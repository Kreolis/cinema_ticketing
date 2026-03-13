import csv
from datetime import datetime
from datetime import timedelta
from io import StringIO

from django.contrib import admin
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase
from django.utils import timezone

from branding.models import Branding
from events.admin import EventAdmin
from events.models import Event, Location


class EventAdminDownloadTemplateCsvTests(TestCase):

    def setUp(self):
        self.request_factory = RequestFactory()
        self.event_admin = EventAdmin(Event, admin.site)
        self.location = Location.objects.create(name='Main Hall', total_seats=100)
        self.admin_user = get_user_model().objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='password',
        )

    def _download_rows(self):
        response = self.event_admin.download_template_csv(self.request_factory.get('/admin/events/event/download-template-csv/'))
        content = response.content.decode('utf-8')
        return list(csv.DictReader(StringIO(content)))

    def _build_import_request(self, csv_content):
        request = self.request_factory.post(
            '/admin/events/event/import-csv/',
            {'csv_file': SimpleUploadedFile('events.csv', csv_content.encode('utf-8'), content_type='text/csv')},
        )
        request.user = self.admin_user

        session_middleware = SessionMiddleware(lambda req: None)
        session_middleware.process_request(request)
        request.session.save()
        setattr(request, '_messages', FallbackStorage(request))
        return request

    def test_download_template_csv_leaves_unset_custom_overrides_blank(self):
        branding_presale_start = timezone.now().replace(microsecond=0)
        Branding.objects.create(
            name='Active Branding',
            is_active=True,
            display_seat_number=False,
            allow_presale=False,
            presale_start=branding_presale_start,
            presale_ends_before=5,
            allow_door_selling=False,
        )
        event = Event.objects.create(
            name='Branding Defaults Event',
            start_time=timezone.now().replace(microsecond=0),
            duration=timedelta(hours=2),
            location=self.location,
        )

        exported_event = next(row for row in self._download_rows() if row['name'] == event.name)

        self.assertEqual(exported_event['location_total_seats'], '100')
        self.assertEqual(exported_event['display_seat_number'], '')
        self.assertEqual(exported_event['allow_presale'], '')
        self.assertEqual(exported_event['presale_start'], '')
        self.assertEqual(exported_event['presale_ends_before'], '')
        self.assertEqual(exported_event['allow_door_selling'], '')

    def test_download_template_csv_exports_explicit_custom_overrides(self):
        custom_presale_start = timezone.now().replace(microsecond=0)
        event = Event.objects.create(
            name='Custom Overrides Event',
            start_time=timezone.now().replace(microsecond=0),
            duration=timedelta(hours=2),
            location=self.location,
            custom_display_seat_number=False,
            custom_allow_presale=False,
            custom_presale_start=custom_presale_start,
            custom_presale_ends_before=3,
            custom_allow_door_selling=False,
        )

        exported_event = next(row for row in self._download_rows() if row['name'] == event.name)

        self.assertEqual(exported_event['location_total_seats'], '100')
        self.assertEqual(exported_event['display_seat_number'], 'False')
        self.assertEqual(exported_event['allow_presale'], 'False')
        self.assertEqual(exported_event['start_time'], event.start_time.isoformat(sep=' '))
        self.assertEqual(exported_event['presale_start'], custom_presale_start.isoformat(sep=' '))
        self.assertEqual(exported_event['presale_ends_before'], '3')
        self.assertEqual(exported_event['allow_door_selling'], 'False')

    def test_import_csv_creates_missing_location_when_location_total_seats_is_provided(self):
        csv_content = (
            'name,start_time,duration,location,location_total_seats,price_classes,program_link,is_active,custom_seats,custom_ticket_background,display_seat_number,custom_event_background,allow_presale,presale_start,presale_ends_before,allow_door_selling,custom_event_timezone\n'
            'Imported Event,2026-03-20 18:00:00,2:00,New Venue,250,,http://example.com,True,,,,,,,,\n'
        )

        response = self.event_admin.import_csv(self._build_import_request(csv_content))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Event.objects.filter(name='Imported Event').exists())
        self.assertTrue(Location.objects.filter(name='New Venue', total_seats=250).exists())

    def test_import_csv_rejects_missing_location_total_seats_for_new_location(self):
        csv_content = (
            'name,start_time,duration,location,location_total_seats,price_classes,program_link,is_active,custom_seats,custom_ticket_background,display_seat_number,custom_event_background,allow_presale,presale_start,presale_ends_before,allow_door_selling,custom_event_timezone\n'
            'Imported Event,2026-03-20 18:00:00,2:00,Missing Venue,,,http://example.com,True,,,,,,,,\n'
        )

        response = self.event_admin.import_csv(self._build_import_request(csv_content))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Provide location_total_seats in the CSV or create the location first.')
        self.assertFalse(Event.objects.filter(name='Imported Event').exists())
        self.assertFalse(Location.objects.filter(name='Missing Venue').exists())

    def test_import_csv_accepts_offset_aware_timestamps_from_export(self):
        start_time = timezone.now().replace(microsecond=0)
        presale_start = (start_time - timedelta(days=1)).replace(microsecond=0)
        csv_content = (
            'name,start_time,duration,location,location_total_seats,price_classes,program_link,is_active,custom_seats,custom_ticket_background,display_seat_number,custom_event_background,allow_presale,presale_start,presale_ends_before,allow_door_selling,custom_event_timezone\n'
            f'Imported Aware Event,{start_time.isoformat(sep=" ")},2:00,New Venue,250,,http://example.com,True,,,False,,True,{presale_start.isoformat(sep=" ")},3,False,\n'
        )

        response = self.event_admin.import_csv(self._build_import_request(csv_content))

        self.assertEqual(response.status_code, 302)
        imported_event = Event.objects.get(name='Imported Aware Event')
        self.assertEqual(imported_event.start_time, start_time)
        self.assertEqual(imported_event.custom_presale_start, presale_start)
        self.assertFalse(imported_event.custom_display_seat_number)
        self.assertTrue(imported_event.custom_allow_presale)
        self.assertEqual(imported_event.custom_presale_ends_before, 3)
        self.assertFalse(imported_event.custom_allow_door_selling)


class EventTimezoneConversionTests(TestCase):

    def setUp(self):
        self.location = Location.objects.create(name='Timezone Hall', total_seats=120)

    def test_naive_datetime_is_interpreted_in_default_branding_timezone(self):
        Branding.objects.create(
            name='Timezone Branding',
            is_active=True,
            default_event_timezone='Europe/Helsinki',
        )
        event = Event.objects.create(
            name='Timezone Event',
            start_time=timezone.now(),
            duration=timedelta(hours=1),
            location=self.location,
        )

        converted = event._convert_to_event_timezone(datetime(2026, 1, 15, 10, 30, 0))

        self.assertEqual(converted.hour, 10)
        self.assertEqual(converted.minute, 30)
        self.assertEqual(converted.tzinfo.zone, 'Europe/Helsinki')

    def test_naive_datetime_uses_custom_event_timezone_when_set(self):
        event = Event.objects.create(
            name='Custom Timezone Event',
            start_time=timezone.now(),
            duration=timedelta(hours=1),
            location=self.location,
            custom_event_timezone='America/New_York',
        )

        converted = event._convert_to_event_timezone(datetime(2026, 1, 15, 10, 30, 0))

        self.assertEqual(converted.hour, 10)
        self.assertEqual(converted.minute, 30)
        self.assertEqual(converted.tzinfo.zone, 'America/New_York')
