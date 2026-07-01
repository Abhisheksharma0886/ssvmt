def portal_context(request):
    from portal.models import SiteConfig
    config, _ = SiteConfig.objects.get_or_create(id=1)
    context = {
        'config': config,
    }

    if request.user.is_authenticated:
        from portal.models import Message
        
        # Count unique senders who sent unread messages to this user
        unread_senders = Message.objects.filter(recipient=request.user, is_read=False).values('sender').distinct().count()
        
        # Construct a map of sender_id -> unread count for contact list rendering
        unread_counts = {}
        unread_messages = Message.objects.filter(recipient=request.user, is_read=False)
        for msg in unread_messages:
            unread_counts[msg.sender_id] = unread_counts.get(msg.sender_id, 0) + 1
            
        context.update({
            'unread_senders_count': unread_senders,
            'unread_counts_map': unread_counts,
        })
    return context
