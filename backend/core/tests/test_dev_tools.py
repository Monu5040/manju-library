import pytest
from django.core.management import CommandError, call_command
from django.test import override_settings

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("environment", ["staging", "production"])
@pytest.mark.parametrize("command", ["seed_demo", "loadtest"])
def test_demo_and_load_tools_refuse_real_servers(command, environment):
    with override_settings(ENVIRONMENT=environment), pytest.raises(CommandError):
        call_command(command)


@override_settings(ENVIRONMENT="development")
def test_seed_demo_makes_a_small_made_up_library(branch):
    from members.models import Student

    call_command("seed_demo", students=5)
    assert Student.objects.filter(full_name__startswith="Demo Student").count() == 5
    with pytest.raises(CommandError):
        call_command("seed_demo", students=5)  # never twice into one database
