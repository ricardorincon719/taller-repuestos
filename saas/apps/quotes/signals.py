from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Quote, QuoteItem


@receiver((post_save, post_delete), sender=QuoteItem)
def refresh_quote_totals(sender, instance, **kwargs):
    quote = Quote.objects.filter(pk=instance.quote_id).first()
    if quote is not None:
        quote.recalculate_totals()
