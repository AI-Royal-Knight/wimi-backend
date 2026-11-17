import factory
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.authentication.models import OTPCode, PasswordResetToken

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@tiboutik.com")
    phone = factory.Sequence(lambda n: f"+5091234{n:04d}")
    full_name = factory.Faker("name")
    is_active = True
    is_verified = True
    terms_accepted = True
    terms_accepted_at = factory.LazyFunction(timezone.now)

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        pw = extracted or "StrongPass123!"
        self.set_password(pw)
        if create:
            self.save()


class OTPCodeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = OTPCode

    user = factory.SubFactory(UserFactory)
    destination = factory.SelfAttribute("user.email")
    code = "1234"
    purpose = OTPCode.PURPOSE_SIGNUP
    channel = OTPCode.CHANNEL_EMAIL
    expires_at = factory.LazyFunction(lambda: timezone.now() + timezone.timedelta(minutes=10))
    is_used = False
    attempts = 0
