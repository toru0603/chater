#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { DynamoStack } from '../stacks/dynamo-stack';
import { ApiStack } from '../stacks/api-stack';
import { WebSocketStack } from '../stacks/websocket-stack';

const app = new cdk.App();
const env = { account: process.env.CDK_DEFAULT_ACCOUNT, region: process.env.CDK_DEFAULT_REGION || 'ap-northeast-1' };

new DynamoStack(app, 'ChaterDynamoStack', { env });
const wsStack = new WebSocketStack(app, 'ChaterWebSocketStack', { env });
new ApiStack(app, 'ChaterApiStack', { env, wsUrl: wsStack.wsUrl });
