import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from .models import Message, MessageAttachment
from asgiref.sync import sync_to_async


class MessagingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        """Handle WebSocket connection"""
        self.user = self.scope['user']
        
        if not self.user.is_authenticated:
            await self.close()
            return
        
        # Create a unique room name for this user
        self.room_name = f"user_{self.user.id}_messages"
        self.room_group_name = self.room_name
        
        # Join the user's message channel group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        print(f"User {self.user.username} connected to messaging")

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
        print(f"User {self.user.username} disconnected from messaging")

    async def receive(self, text_data):
        """Receive message from WebSocket"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'send_message':
                await self.handle_send_message(data)
            elif message_type == 'mark_as_read':
                await self.handle_mark_as_read(data)
            elif message_type == 'get_unread_count':
                await self.handle_get_unread_count()
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'error': 'Invalid JSON'
            }))

    async def handle_send_message(self, data):
        """Handle incoming message from user"""
        recipient_id = data.get('recipient_id')
        subject = data.get('subject', '')
        content = data.get('content', '')
        
        try:
            # Save message to database
            message = await self.save_message(recipient_id, subject, content)
            
            if message:
                recipient_room = f"user_{recipient_id}_messages"
                message_data = {
                    'type': 'new_message',
                    'message_id': message.id,
                    'sender': self.user.get_full_name() or self.user.username,
                    'sender_id': self.user.id,
                    'subject': subject or 'No Subject',
                    'content': content,
                    'created_at': message.created_at.strftime('%Y-%m-%d %H:%M'),
                    'is_read': False,
                    'attachments': []
                }
                
                # Send notification to recipient
                await self.channel_layer.group_send(
                    recipient_room,
                    {
                        'type': 'new_message',
                        'data': message_data
                    }
                )
                
                # Send confirmation to sender
                await self.send(text_data=json.dumps({
                    'type': 'message_sent',
                    'message_id': message.id,
                    'status': 'success'
                }))
        except Exception as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'error': str(e)
            }))

    async def handle_mark_as_read(self, data):
        """Mark a message as read"""
        message_id = data.get('message_id')
        try:
            await self.mark_message_as_read(message_id)
            await self.send(text_data=json.dumps({
                'type': 'message_read',
                'message_id': message_id,
                'status': 'success'
            }))
        except Exception as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'error': str(e)
            }))

    async def handle_get_unread_count(self):
        """Get unread message count"""
        try:
            unread_count = await self.get_unread_count()
            await self.send(text_data=json.dumps({
                'type': 'unread_count',
                'unread_count': unread_count
            }))
        except Exception as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'error': str(e)
            }))

    # Database operations
    @database_sync_to_async
    def save_message(self, recipient_id, subject, content):
        """Save message to database"""
        try:
            recipient = User.objects.get(id=recipient_id)
            message = Message.objects.create(
                sender=self.user,
                recipient=recipient,
                subject=subject,
                content=content,
                is_read=False
            )
            return message
        except User.DoesNotExist:
            return None

    @database_sync_to_async
    def mark_message_as_read(self, message_id):
        """Mark message as read"""
        try:
            message = Message.objects.get(id=message_id)
            if message.recipient == self.user:
                message.is_read = True
                message.save()
        except Message.DoesNotExist:
            pass

    @database_sync_to_async
    def get_unread_count(self):
        """Get count of unread messages"""
        return Message.objects.filter(
            recipient=self.user,
            is_read=False
        ).count()

    # Receive message from group (for broadcasting)
    async def new_message(self, event):
        """Send new message to WebSocket"""
        data = event.get('data')
        await self.send(text_data=json.dumps({
            'type': 'new_message',
            'data': data
        }))
