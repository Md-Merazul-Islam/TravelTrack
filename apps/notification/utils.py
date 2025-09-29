from .models import Notification

def create_notification(user, title, message):
    """
    Universal helper to create a notification.
    """
    return Notification.objects.create(user=user, title=title, message=message)

def send_notification(user, title, message):
    """
    Universal helper to send a notification.
    """
    return create_notification(user, title, message)