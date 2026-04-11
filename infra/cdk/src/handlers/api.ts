import { APIGatewayProxyEvent, APIGatewayProxyResult } from 'aws-lambda';
import { DynamoDBClient } from '@aws-sdk/client-dynamodb';
import { DynamoDBDocumentClient, ScanCommand, PutCommand } from '@aws-sdk/lib-dynamodb';

const client = new DynamoDBClient({});
const ddb = DynamoDBDocumentClient.from(client);

export const handler = async (event: APIGatewayProxyEvent): Promise<APIGatewayProxyResult> => {
  const tableName = process.env.TABLE_NAME || '';
  try {
    if (event.httpMethod === 'GET') {
      const res = await ddb.send(new ScanCommand({ TableName: tableName, Limit: 50 }));
      return { statusCode: 200, body: JSON.stringify({ items: res.Items || [] }) };
    } else if (event.httpMethod === 'POST') {
      const body = event.body ? JSON.parse(event.body) : {};
      const pk = body.pk || `ITEM#${Date.now()}`;
      const sk = body.sk || 'META';
      await ddb.send(new PutCommand({ TableName: tableName, Item: { PK: pk, SK: sk, data: body } }));
      return { statusCode: 201, body: JSON.stringify({ pk, sk }) };
    } else {
      return { statusCode: 405, body: 'Method Not Allowed' };
    }
  } catch (e) {
    console.error(e);
    return { statusCode: 500, body: JSON.stringify({ error: String(e) }) };
  }
};
