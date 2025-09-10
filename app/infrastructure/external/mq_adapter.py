import pika
import json
from typing import Optional, Dict
import os
from app.application.interfaces import MessageQueueInterface


class RabbitMQAdapter(MessageQueueInterface):
    """RabbitMQ adapter implementation"""
    
    def __init__(self, host: str = None, port: int = None, username: str = None, password: str = None):
        self.host = host or os.getenv("RABBITMQ_HOST", "localhost")
        self.port = port or int(os.getenv("RABBITMQ_PORT", "5672"))
        self.username = username or os.getenv("RABBITMQ_USERNAME", "guest")
        self.password = password or os.getenv("RABBITMQ_PASSWORD", "guest")
        
        self.credentials = pika.PlainCredentials(self.username, self.password)
        self.connection_params = pika.ConnectionParameters(
            host=self.host,
            port=self.port,
            credentials=self.credentials
        )
    
    def _get_connection(self):
        """Get a connection to RabbitMQ"""
        return pika.BlockingConnection(self.connection_params)
    
    async def publish_message(self, queue_name: str, message: dict) -> bool:
        """Publish a message to the specified queue"""
        try:
            connection = self._get_connection()
            channel = connection.channel()
            
            # Declare queue if it doesn't exist
            channel.queue_declare(queue=queue_name, durable=True)
            
            # Publish message
            channel.basic_publish(
                exchange='',
                routing_key=queue_name,
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Make message persistent
                )
            )
            
            connection.close()
            return True
        except Exception as e:
            print(f"Failed to publish message: {e}")
            return False
    
    async def consume_message(self, queue_name: str) -> Optional[dict]:
        """Consume a single message from the specified queue"""
        try:
            connection = self._get_connection()
            channel = connection.channel()
            
            # Declare queue if it doesn't exist
            channel.queue_declare(queue=queue_name, durable=True)
            
            # Get a single message
            method_frame, header_frame, body = channel.basic_get(
                queue=queue_name,
                auto_ack=True
            )
            
            connection.close()
            
            if method_frame:
                return json.loads(body.decode('utf-8'))
            return None
        except Exception as e:
            print(f"Failed to consume message: {e}")
            return None
    
    def setup_consumer(self, queue_name: str, callback_function):
        """Set up a continuous consumer for the specified queue"""
        try:
            connection = self._get_connection()
            channel = connection.channel()
            
            # Declare queue if it doesn't exist
            channel.queue_declare(queue=queue_name, durable=True)
            
            # Set up consumer
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(
                queue=queue_name,
                on_message_callback=callback_function
            )
            
            print(f"Starting consumer for queue: {queue_name}")
            channel.start_consuming()
        except Exception as e:
            print(f"Failed to setup consumer: {e}")
    
    def create_exchange(self, exchange_name: str, exchange_type: str = "direct"):
        """Create an exchange"""
        try:
            connection = self._get_connection()
            channel = connection.channel()
            
            channel.exchange_declare(
                exchange=exchange_name,
                exchange_type=exchange_type,
                durable=True
            )
            
            connection.close()
            return True
        except Exception as e:
            print(f"Failed to create exchange: {e}")
            return False
    
    def bind_queue_to_exchange(self, queue_name: str, exchange_name: str, routing_key: str = ""):
        """Bind a queue to an exchange"""
        try:
            connection = self._get_connection()
            channel = connection.channel()
            
            # Declare queue and exchange
            channel.queue_declare(queue=queue_name, durable=True)
            channel.exchange_declare(exchange=exchange_name, exchange_type="direct", durable=True)
            
            # Bind queue to exchange
            channel.queue_bind(
                exchange=exchange_name,
                queue=queue_name,
                routing_key=routing_key
            )
            
            connection.close()
            return True
        except Exception as e:
            print(f"Failed to bind queue to exchange: {e}")
            return False