import { APIGatewayProxyEvent, APIGatewayProxyResult } from 'aws-lambda';
import AWS from 'aws-sdk';

const ddb = new AWS.DynamoDB.DocumentClient();

export const handler = async (event: APIGatewayProxyEvent): Promise<APIGatewayProxyResult> => {
  const tableName = process.env.TABLE_NAME || '';
  try {
    if (event.httpMethod === 'GET') {
      const res = await ddb.scan({ TableName: tableName, Limit: 50 }).promise();
      return { statusCode: 200, body: JSON.stringify({ items: res.Items || [] }) };
    } else if (event.httpMethod === 'POST') {
      const body = event.body ? JSON.parse(event.body) : {};
      const pk = body.pk || `ITEM#${Date.now()}`;
      const sk = body.sk || 'META';
      await ddb.put({ TableName: tableName, Item: { PK: pk, SK: sk, data: body } }).promise();
      return { statusCode: 201, body: JSON.stringify({ pk, sk }) };
    } else {
      return { statusCode: 405, body: 'Method Not Allowed' };
    }
  } catch (e) {
    console.error(e);
    return { statusCode: 500, body: JSON.stringify({ error: String(e) }) };
  }
};
