import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as iam from 'aws-cdk-lib/aws-iam';
import { WebSocketApi, WebSocketStage } from '@aws-cdk/aws-apigatewayv2-alpha';
import { WebSocketLambdaIntegration } from '@aws-cdk/aws-apigatewayv2-integrations-alpha';
import { Construct } from 'constructs';
import * as path from 'path';
import { RemovalPolicy } from 'aws-cdk-lib';

export interface WebSocketStackProps extends cdk.StackProps {
  stage?: string;
}

export class WebSocketStack extends cdk.Stack {
  public readonly wsUrl: string;

  constructor(scope: Construct, id: string, props: WebSocketStackProps) {
    super(scope, id, props);

    const connectionsTable = new dynamodb.Table(this, 'ConnectionsTable', {
      partitionKey: { name: 'connectionId', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: RemovalPolicy.DESTROY,
      timeToLiveAttribute: 'ttl',
    });

    connectionsTable.addGlobalSecondaryIndex({
      indexName: 'RoomCodeIndex',
      partitionKey: { name: 'roomCode', type: dynamodb.AttributeType.STRING },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    const projectRoot = path.join(__dirname, '../../../');

    const wsFn = new lambda.Function(this, 'WsHandler', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'ws_handler.handler',
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
      code: lambda.Code.fromAsset(projectRoot, {
        bundling: {
          image: lambda.Runtime.PYTHON_3_11.bundlingImage,
          command: [
            'bash', '-c',
            'pip install boto3 -t /asset-output --quiet && cp /asset-input/infra/cdk/src/handlers/ws_handler.py /asset-output/',
          ],
        },
      }),
      environment: {
        CONNECTIONS_TABLE: connectionsTable.tableName,
      },
    });

    connectionsTable.grantReadWriteData(wsFn);

    const stageName = (props && props.stage) ? props.stage : 'prod';

    const wsApiName = stageName !== 'prod' ? `ChaterWsApi-${stageName}` : 'ChaterWsApi';

    const wsApi = new WebSocketApi(this, 'WsApi', {
      apiName: wsApiName,
      connectRouteOptions: {
        integration: new WebSocketLambdaIntegration('ConnectIntegration', wsFn),
      },
      disconnectRouteOptions: {
        integration: new WebSocketLambdaIntegration('DisconnectIntegration', wsFn),
      },
      defaultRouteOptions: {
        integration: new WebSocketLambdaIntegration('DefaultIntegration', wsFn),
      },
    });

    const wsStage = new WebSocketStage(this, 'WsStage', {
      webSocketApi: wsApi,
      stageName: stageName,
      autoDeploy: true,
    });

    // Allow Lambda to send messages back via API Gateway Management API
    wsFn.addToRolePolicy(new iam.PolicyStatement({
      actions: ['execute-api:ManageConnections'],
      resources: [
        `arn:aws:execute-api:${this.region}:${this.account}:${wsApi.apiId}/${stageName}/POST/@connections/*`,
      ],
    }));

    this.wsUrl = wsStage.url;

    new cdk.CfnOutput(this, 'WsUrl', { value: wsStage.url });
  }
}
