import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigw from 'aws-cdk-lib/aws-apigateway';
import { Construct } from 'constructs';
import * as path from 'path';

export class ApiStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Project root is 3 levels up from infra/cdk/stacks/
    const projectRoot = path.join(__dirname, '../../../');

    const fn = new lambda.Function(this, 'AppHandler', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'lambda_handler.handler',
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
      code: lambda.Code.fromAsset(projectRoot, {
        bundling: {
          image: lambda.Runtime.PYTHON_3_11.bundlingImage,
          command: [
            'bash', '-c',
            [
              'pip install -r /asset-input/requirements.txt -t /asset-output --quiet',
              'cp -r /asset-input/app /asset-input/templates /asset-input/static /asset-output/',
              'cp /asset-input/infra/cdk/src/handlers/lambda_handler.py /asset-output/',
            ].join(' && '),
          ],
        },
      }),
    });

    const api = new apigw.LambdaRestApi(this, 'RestApi', {
      handler: fn,
      proxy: true,
      restApiName: 'ChaterApi',
      // Allow binary responses (CSS, JS, images)
      binaryMediaTypes: ['*/*'],
    });

    new cdk.CfnOutput(this, 'ApiUrl', { value: api.url });
  }
}
