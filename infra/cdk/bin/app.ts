#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { DynamoStack } from '../stacks/dynamo-stack';
import { ApiStack } from '../stacks/api-stack';
import { WebSocketStack } from '../stacks/websocket-stack';
import { CloudFrontStack } from '../stacks/cloudfront-stack';

const app = new cdk.App();
const stage = app.node.tryGetContext('stage') || process.env.DEPLOY_STAGE || process.env.STAGE || 'prod';
const env = { account: process.env.CDK_DEFAULT_ACCOUNT, region: process.env.CDK_DEFAULT_REGION || 'ap-northeast-1' };

if (stage === 'cloudfront') {
  const prodApiUrl = app.node.tryGetContext('prodApiUrl') as string;
  const devApiUrl = app.node.tryGetContext('devApiUrl') as string;
  if (!prodApiUrl || !devApiUrl) {
    throw new Error('prodApiUrl and devApiUrl context values are required for stage=cloudfront');
  }
  // CloudFront runs globally; use us-east-1 region for the stack itself
  const cfEnv = { account: env.account, region: 'ap-northeast-1' };
  new CloudFrontStack(app, 'ChaterCloudFrontStack', { env: cfEnv, prodApiUrl, devApiUrl });
} else {
  const nameSuffix = stage === 'prod' ? '' : `-${stage}`;
  new DynamoStack(app, `ChaterDynamoStack${nameSuffix}`, { env, stage });
  const wsStack = new WebSocketStack(app, `ChaterWebSocketStack${nameSuffix}`, { env, stage });
  new ApiStack(app, `ChaterApiStack${nameSuffix}`, { env, stage, wsUrl: wsStack.wsUrl });
}
