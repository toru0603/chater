#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { DynamoStack } from '../stacks/dynamo-stack';
import { ApiStack } from '../stacks/api-stack';

const app = new cdk.App();
const env = { account: process.env.CDK_DEFAULT_ACCOUNT, region: process.env.CDK_DEFAULT_REGION || 'us-east-1' };

const dynamoStack = new DynamoStack(app, 'ChaterDynamoStack', { env });
new ApiStack(app, 'ChaterApiStack', { env, table: dynamoStack.table });
