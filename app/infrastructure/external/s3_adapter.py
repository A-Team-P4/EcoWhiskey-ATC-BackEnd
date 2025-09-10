import boto3
from typing import Optional
from botocore.exceptions import ClientError
import os
from app.application.interfaces import S3ServiceInterface


class S3Adapter(S3ServiceInterface):
    """AWS S3 adapter implementation"""
    
    def __init__(self, access_key: str = None, secret_key: str = None, region: str = "us-east-1"):
        self.access_key = access_key or os.getenv("AWS_ACCESS_KEY_ID")
        self.secret_key = secret_key or os.getenv("AWS_SECRET_ACCESS_KEY")
        self.region = region
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region
        )
    
    async def upload_file(self, file_path: str, bucket: str, key: str) -> str:
        """Upload a file to S3 bucket"""
        try:
            self.s3_client.upload_file(file_path, bucket, key)
            return f"s3://{bucket}/{key}"
        except ClientError as e:
            raise Exception(f"Failed to upload file to S3: {e}")
    
    async def download_file(self, bucket: str, key: str, local_path: str) -> bool:
        """Download a file from S3 bucket"""
        try:
            self.s3_client.download_file(bucket, key, local_path)
            return True
        except ClientError as e:
            print(f"Failed to download file from S3: {e}")
            return False
    
    async def delete_file(self, bucket: str, key: str) -> bool:
        """Delete a file from S3 bucket"""
        try:
            self.s3_client.delete_object(Bucket=bucket, Key=key)
            return True
        except ClientError as e:
            print(f"Failed to delete file from S3: {e}")
            return False
    
    def list_objects(self, bucket: str, prefix: str = "") -> list:
        """List objects in S3 bucket with optional prefix"""
        try:
            response = self.s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
            return [obj['Key'] for obj in response.get('Contents', [])]
        except ClientError as e:
            print(f"Failed to list objects in S3: {e}")
            return []
    
    def generate_presigned_url(self, bucket: str, key: str, expiration: int = 3600) -> Optional[str]:
        """Generate a presigned URL for S3 object"""
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket, 'Key': key},
                ExpiresIn=expiration
            )
            return url
        except ClientError as e:
            print(f"Failed to generate presigned URL: {e}")
            return None