from datetime import timedelta

import pytest
from django.utils import timezone

from apps.core.models import SchedulerLock
from apps.core.scheduler import acquire_lock, release_lock


@pytest.mark.django_db
def test_only_one_worker_gets_the_lock():
    assert acquire_lock("job", 60, owner="worker-a") is True
    assert acquire_lock("job", 60, owner="worker-b") is False
    assert acquire_lock("job", 60, owner="worker-a") is True  # owner can renew


@pytest.mark.django_db
def test_expired_or_released_lock_can_be_taken():
    SchedulerLock.objects.create(
        job_name="job", locked_until=timezone.now() - timedelta(seconds=1), locked_by="dead"
    )
    assert acquire_lock("job", 60, owner="worker-b") is True
    release_lock("job", owner="worker-b")
    assert acquire_lock("job", 60, owner="worker-c") is True
