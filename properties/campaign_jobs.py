"""Background campaign jobs: daily content reminders + auto-complete."""

from __future__ import annotations

from django.utils import timezone

from .models import CampaignCollaborator, CampaignTaskMessage, MarketingCampaign


def _seller_label(campaign):
    prop = campaign.property
    owner = getattr(prop, 'owner', None)
    owner_name = ''
    if owner is not None:
        owner_name = owner.get_full_name() or owner.username
    return owner_name or prop.title


def build_reminder_message(campaign, today, done):
    seller = _seller_label(campaign)
    note = (campaign.content_reminder_note or '').strip()
    needed_photos = campaign.photos_per_day
    needed_videos = campaign.videos_per_day
    parts = [
        f'Today ({today:%d %b %Y}) your campaign "{campaign.title}" still needs content '
        f'for seller/property "{seller}".',
        f'Required today: {needed_photos} photo post(s) and {needed_videos} video post(s).',
        f'Logged so far today: {done["photos"]} photo(s), {done["videos"]} video(s).',
    ]
    if note:
        parts.append(f'Note from campaign owner: {note}')
    else:
        parts.append(
            'Please create and publish a video/photo post for this seller today.'
        )
    return '\n'.join(parts)


def send_missing_content_reminders(today=None):
    """Create one task message per collaborator when daily targets are not met."""
    today = today or timezone.localdate()
    created = 0
    campaigns = MarketingCampaign.objects.filter(status='active').select_related(
        'property', 'property__owner'
    )
    for campaign in campaigns:
        if campaign.photos_per_day == 0 and campaign.videos_per_day == 0:
            continue
        if campaign.start_date and campaign.start_date > today:
            continue
        if campaign.end_date and campaign.end_date < today:
            continue

        done = campaign.content_done_for_date(today)
        photos_ok = done['photos'] >= campaign.photos_per_day
        videos_ok = done['videos'] >= campaign.videos_per_day
        if photos_ok and videos_ok:
            continue

        message = build_reminder_message(campaign, today, done)
        collabs = (
            CampaignCollaborator.objects.filter(campaign=campaign, accepted=True)
            .exclude(role='owner')
            .select_related('user')
        )
        if not collabs.exists():
            collabs = CampaignCollaborator.objects.filter(
                campaign=campaign, accepted=True
            ).select_related('user')

        for collab in collabs:
            _, was_created = CampaignTaskMessage.objects.get_or_create(
                campaign=campaign,
                recipient=collab.user,
                work_date=today,
                defaults={'message': message, 'is_read': False},
            )
            if was_created:
                created += 1
    return created


def auto_complete_campaigns(today=None):
    """Mark active campaigns completed when end date passed and all posts are done."""
    today = today or timezone.localdate()
    completed = 0
    for campaign in MarketingCampaign.objects.filter(status='active'):
        if campaign.should_auto_complete(today=today):
            campaign.status = 'completed'
            update_fields = ['status']
            if hasattr(campaign, 'updated_at'):
                update_fields.append('updated_at')
            campaign.save(update_fields=update_fields)
            completed += 1
    return completed


def run_jobs_for_campaign(campaign, today=None):
    """Run reminder/auto-complete logic for a single campaign."""
    today = today or timezone.localdate()
    reminders = 0
    completed = 0
    if campaign.status == 'active':
        if campaign.photos_per_day or campaign.videos_per_day:
            if (
                (not campaign.start_date or campaign.start_date <= today)
                and (not campaign.end_date or campaign.end_date >= today)
            ):
                done = campaign.content_done_for_date(today)
                photos_ok = done['photos'] >= campaign.photos_per_day
                videos_ok = done['videos'] >= campaign.videos_per_day
                if not (photos_ok and videos_ok):
                    message = build_reminder_message(campaign, today, done)
                    collabs = (
                        CampaignCollaborator.objects.filter(campaign=campaign, accepted=True)
                        .exclude(role='owner')
                        .select_related('user')
                    )
                    if not collabs.exists():
                        collabs = CampaignCollaborator.objects.filter(
                            campaign=campaign, accepted=True
                        ).select_related('user')
                    for collab in collabs:
                        _, was_created = CampaignTaskMessage.objects.get_or_create(
                            campaign=campaign,
                            recipient=collab.user,
                            work_date=today,
                            defaults={'message': message, 'is_read': False},
                        )
                        if was_created:
                            reminders += 1
        if campaign.should_auto_complete(today=today):
            campaign.status = 'completed'
            update_fields = ['status']
            if hasattr(campaign, 'updated_at'):
                update_fields.append('updated_at')
            campaign.save(update_fields=update_fields)
            completed = 1
    return {'reminders': reminders, 'completed': completed, 'date': today}


def run_campaign_jobs(today=None):
    today = today or timezone.localdate()
    reminders = send_missing_content_reminders(today=today)
    completed = auto_complete_campaigns(today=today)
    return {'reminders': reminders, 'completed': completed, 'date': today}
