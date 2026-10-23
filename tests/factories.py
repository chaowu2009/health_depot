import factory
from django.utils import timezone

from apps.accounts.models import User
from apps.clients.models import Client
from apps.forms_builder.models import FormTemplate
from apps.organizations.models import Division, Organization, Program
from apps.referrals.models import Referral


class OrganizationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Organization

    name = factory.Sequence(lambda n: f"Fictional Partner {n}")
    slug = factory.Sequence(lambda n: f"partner-{n}")
    org_type = Organization.OrgType.COMMUNITY_PARTNER


class HealthDepartmentFactory(OrganizationFactory):
    class Meta:
        model = Organization
        django_get_or_create = ("slug",)

    name = "Calvert County Health Department"
    slug = "cchd"
    org_type = Organization.OrgType.HEALTH_DEPARTMENT


class DivisionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Division

    organization = factory.SubFactory(HealthDepartmentFactory)
    name = factory.Sequence(lambda n: f"Division {n}")
    code = factory.Sequence(lambda n: f"D{n}")


class ProgramFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Program

    division = factory.SubFactory(DivisionFactory)
    name = factory.Sequence(lambda n: f"Program {n}")
    code = factory.Sequence(lambda n: f"P{n}")


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"user{n}@example.test")
    first_name = "Test"
    last_name = factory.Sequence(lambda n: f"User{n}")
    role = User.Role.STAFF
    password = factory.PostGenerationMethodCall("set_password", "a-long-test-password-123")

    @factory.post_generation
    def _save(obj, create, extracted, **kwargs):  # noqa: N805
        if create:
            obj.save()


class ClientFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Client

    first_name = "Synthetic"
    last_name = factory.Sequence(lambda n: f"Person{n}")
    date_of_birth = factory.LazyFunction(lambda: timezone.now().date().replace(year=1985))


class FormTemplateFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = FormTemplate

    name = "General Intake"
    owner_organization = factory.SubFactory(HealthDepartmentFactory)
    fields = factory.LazyFunction(
        lambda: [{"key": "need", "label": "What do you need help with?", "type": "long_text"}]
    )


class ReferralFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Referral

    reference_number = factory.Sequence(lambda n: f"CR-2026-{n:06d}")
    client = factory.SubFactory(ClientFactory)
    program = factory.SubFactory(ProgramFactory)
    direction = Referral.Direction.INBOUND
    sending_organization = factory.SubFactory(OrganizationFactory)
    receiving_organization = factory.LazyAttribute(lambda o: o.program.division.organization)
