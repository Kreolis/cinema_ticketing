from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import FileResponse, JsonResponse
from django.conf import settings
from django.utils import timezone as django_timezone

from django.utils.translation import gettext as _

import io
import logging
from datetime import datetime, timezone
from decimal import Decimal
from fpdf import FPDF

logger = logging.getLogger(__name__)

from payments import get_payment_model
from payments.models import PaymentStatus
from accounting.models import get_order_create_defaults


from .models import Event, Ticket, SoldAsStatus, Location
from .models import get_user_active_locations, is_admin_user, is_user_in_ticket_managers_group_or_admin, is_user_in_ticket_managers_or_checkers_group_or_admin
from branding.models import get_active_branding
from .forms import TicketSelectionForm

def event_list(request):
    # Retrieve all events, you can filter if they are active
    events = Event.objects.filter(is_active=True).order_by('start_time')
    selected_location_id = request.GET.get('location')
    selected_day = request.GET.get('day')

    is_special_staff_user = is_user_in_ticket_managers_or_checkers_group_or_admin(request.user)

    # restrict the events shown to ticket managers to only those that are in their active locations if they have any
    if is_special_staff_user:
        active_locations = get_user_active_locations(request.user)
        if active_locations is not None and active_locations.exists():
            events = events.filter(location__in=active_locations)

    location_options = Location.objects.filter(event__in=events).distinct().order_by('name')

    if selected_location_id:
        events = events.filter(location_id=selected_location_id)

    day_options = events.values_list('start_time__date', flat=True).distinct().order_by('start_time__date')

    if selected_day:
        try:
            day_date = datetime.strptime(selected_day, '%Y-%m-%d').date()
            events = events.filter(start_time__date=day_date)
        except ValueError:
            selected_day = ''

    return render(request, 'event_list.html', {
        'events': events,
        'currency': settings.DEFAULT_CURRENCY,
        'is_special_staff_user': is_special_staff_user,
        'location_options': location_options,
        'selected_location_id': selected_location_id,
        'selected_day': selected_day,
        'day_options': day_options
    })

# Event detail view with ticket selection
def event_detail(request, event_id):
    event = get_object_or_404(Event, id=event_id)

    branding = get_active_branding()

    # Check ticket manager access early, before any POST processing
    is_special_staff_user = is_user_in_ticket_managers_or_checkers_group_or_admin(request.user)
    if is_special_staff_user:
        active_locations = get_user_active_locations(request.user)
        if active_locations is not None and active_locations.exists() and event.location not in active_locations:
            return redirect('event_list')

    # select all price classes for the event apart from secret ones
    price_classes = event.price_classes.all().exclude(secret=True)

    if branding and branding.use_online_presale_end and branding.online_presale_end:
        presale_end_time = branding.presale_end_time_in_timezone
    else:
        presale_end_time = event.presale_end_time_in_timezone

    # Ensure the session is created
    if not request.session.session_key:
        request.session.create()

    if request.method == 'POST':
        if (presale_end_time < datetime.now(timezone.utc)) or (not event.check_active()):
            # Presale has ended or is inactive
            return JsonResponse({"status": "error", "message": _("Presale has ended for this event.")})
        
        if event.presale_start > datetime.now(timezone.utc):
            # Presale has not started yet
            return JsonResponse({"status": "error", "message": _("Presale has not started yet.")})
        
        form = TicketSelectionForm(request.POST, price_classes=price_classes)
        if form.is_valid():
            selected_tickets = []
            for price_class in price_classes:
                quantity = form.cleaned_data.get(f'quantity_{price_class.id}', 0)
                if quantity > 0:
                    for _ in range(quantity):
                        new_ticket = Ticket(
                            event=event,
                            price_class=price_class,
                            activated=False,
                            sold_as=SoldAsStatus.WAITING
                        )
                        new_ticket.save()
                        selected_tickets.append(new_ticket)
                        
            order, _  = get_payment_model().objects.get_or_create(
                session_id=request.session.session_key,
                defaults=get_order_create_defaults(),
            )
            order.update_tickets(selected_tickets)
            
    else:
        form = TicketSelectionForm(price_classes=price_classes)

    return render(request, 'event_details.html', {
        'event': event,
        'event_active': event.check_active(),
        'price_classes': price_classes,
        'form': form,
        'is_special_staff_user': is_special_staff_user,
        'presale_end_time': presale_end_time,
        'presale_start_time': event.presale_start_time_in_timezone,
        'currency': settings.DEFAULT_CURRENCY,
    })

# user ticket controls during order
def update_ticket_email(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    if request.method == 'POST':
        new_email = request.POST.get('email')
        if new_email:
            ticket.email = new_email
            ticket.save()
            return JsonResponse({"status": "success", "message": "Email updated to " + ticket.email, "updated_email": ticket.email})
    return JsonResponse({"status": "error", "message": "Invalid request"})

def update_ticket_name(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    if request.method == 'POST':
        new_first_name = request.POST.get('first_name')
        new_last_name = request.POST.get('last_name')
        if new_first_name is not None or new_last_name is not None:
            if new_first_name is not None:
                ticket.first_name = new_first_name
            if new_last_name is not None:
                ticket.last_name = new_last_name
            ticket.save()
            full_name = f"{ticket.first_name or ''} {ticket.last_name or ''}".strip()
            return JsonResponse({
                "status": "success",
                "message": "Name updated to " + full_name,
                "updated_first_name": ticket.first_name,
                "updated_last_name": ticket.last_name
            })
    return JsonResponse({"status": "error", "message": "Invalid request"})

def delete_ticket(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    order = get_object_or_404(get_payment_model(), session_id=request.session.session_key)
    order.delete_ticket(ticket)
    
    # Return JSON response with updated order data
    return JsonResponse({
        "status": "success",
        "new_total": f"{order.total} {settings.DEFAULT_CURRENCY}",
        "ticket_count": order.tickets.count()
    })

def show_generated_ticket_pdf(request, ticket_id):
    # Fetch the ticket by ID
    ticket = Ticket.objects.get(pk=ticket_id)
    
    # Generate PDF for the selected ticket
    pdf = ticket.generate_pdf_ticket()
    # Create a BytesIO stream to hold the PDF data
    file_stream = io.BytesIO(pdf.output())

    # Create a FileResponse to send the PDF file
    response = FileResponse(file_stream, content_type='application/pdf', filename=f"ticket_{ticket.id}.pdf")
    
    return response

def send_ticket_email(request, ticket_id):
    ticket = get_object_or_404(Ticket, pk=ticket_id)
    if ticket.email:
        try:
            ticket.queue_send_to_email()
            return JsonResponse({'status': 'success', 'message': _('Email queued successfully.')})
        except Exception as e:
            logger.exception("Failed to queue ticket email for ticket_id=%s: %s", ticket_id, e)
            return JsonResponse({'status': 'error', 'message': _('An error occurred while queueing the email.')}, status=500)
    return JsonResponse({"status": "error", "message": _("No email address provided.")})

@login_required
@user_passes_test(is_user_in_ticket_managers_or_checkers_group_or_admin)
def event_check_in(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    # filter out waiting tickets = not sold yet, SoldAsStatus.PRESALE_ONLINE_WAITING and SoldAsStatus.WAITING
    tickets = Ticket.objects.filter(event=event).exclude(sold_as__in=[SoldAsStatus.PRESALE_ONLINE_WAITING, SoldAsStatus.WAITING])
    branding = get_active_branding()

    return render(request, 'event_check_in.html', {
        'event': event,
        'event_active': event.check_active(),
        'tickets': tickets,
        'branding': branding,
        'currency': settings.DEFAULT_CURRENCY
    })

@login_required
@user_passes_test(is_user_in_ticket_managers_or_checkers_group_or_admin)
def handle_qr_result(request, event_id):
    if request.method == "POST":
        qr_code_data = request.POST.get('qr_code')
        try:
            ticket = Ticket.objects.get(id=qr_code_data, event_id=event_id)
            if ticket.activated:
                return JsonResponse({"status": "error", "message": "Ticket already activated"})
            ticket.activated = True
            ticket.save()
            return JsonResponse({"status": "success", "activated": ticket.activated, "ticket_id": str(ticket.id)})
        except Ticket.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Ticket not found"})
    return JsonResponse({"status": "error", "message": "Invalid request"})

@login_required
@user_passes_test(is_user_in_ticket_managers_or_checkers_group_or_admin)
def toggle_ticket_activation(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    ticket.activated = not ticket.activated
    ticket.save()
    return JsonResponse({"status": "success", "activated": ticket.activated})

@login_required
@user_passes_test(is_user_in_ticket_managers_group_or_admin)
def event_door_selling(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    price_classes = event.price_classes.all()

    presale_end_time = event.presale_end_time_in_timezone

    if request.method == 'POST':
        form = TicketSelectionForm(request.POST, price_classes=price_classes, display_name_fields=True)
        if form.is_valid():
            if event.check_active():
                # event is active: all good.
                for price_class in price_classes:
                    quantity = form.cleaned_data.get(f'quantity_{price_class.id}', 0)
                    if quantity > 0:
                        for _ in range(quantity):
                            if presale_end_time < datetime.now(timezone.utc):
                                # Presale has ended
                                
                                if event.allow_door_selling:
                                    # sell tickets as DOOR
                                    new_ticket = Ticket(
                                        event=event,
                                        price_class=price_class,
                                        activated=True,
                                        sold_as=SoldAsStatus.DOOR,
                                        email=form.cleaned_data.get('email'),
                                        first_name=form.cleaned_data.get('first_name'),
                                        last_name=form.cleaned_data.get('last_name')
                                    )
                                else:
                                    # Door selling is not allowed
                                    return JsonResponse({"status": "error", "message": _("Door selling is not allowed for this event.")})
                            else:
                                # Sell tickets as PRESALE
                                new_ticket = Ticket(
                                    event=event,
                                    price_class=price_class,
                                    activated=False,
                                    sold_as=SoldAsStatus.PRESALE_DOOR,
                                    email=form.cleaned_data.get('email'),
                                    first_name=form.cleaned_data.get('first_name'),
                                    last_name=form.cleaned_data.get('last_name')
                                )
                            new_ticket.save()

                            # if email is provided, send the ticket email
                            if new_ticket.email:
                                try:
                                    new_ticket.queue_send_to_email()
                                except Exception as e:
                                    logger.exception("Failed to queue ticket email for ticket_id=%s: %s", new_ticket.id, e)
            else:
                # event is not active
                return JsonResponse({"status": "error", "message": _("Event is not active.")})
            
    form = TicketSelectionForm(price_classes=price_classes, display_name_fields=True)

    tickets_door_and_presale = Ticket.objects.filter(event=event).filter(sold_as__in=[SoldAsStatus.DOOR, SoldAsStatus.PRESALE_DOOR])

    return render(request, 'event_door_selling.html', {
        'event': event,
        'event_active': event.check_active(),
        'presale_end_time': presale_end_time,
        'presale_start_time': event.presale_start_time_in_timezone,
        'price_classes': price_classes,
        'tickets_door_and_presale': tickets_door_and_presale,
        'form': form,
        'currency': settings.DEFAULT_CURRENCY
    })

@login_required
@user_passes_test(is_user_in_ticket_managers_group_or_admin)
def event_statistics(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    total_stats, price_class_stats = event.calculate_statistics()
    return render(request, 'event_statistics.html', {
        'price_class_stats': price_class_stats,
        'total_stats': total_stats,
        'event': event,
        'currency': settings.DEFAULT_CURRENCY
    })

@login_required
@user_passes_test(is_user_in_ticket_managers_group_or_admin)
def show_generated_statistics_pdf(request, event_id):
    # Fetch the event by ID
    event = Event.objects.get(pk=event_id)
    
    # Generate PDF for the selected ticket
    pdf = event.generate_statistics_pdf()
    # Create a BytesIO stream to hold the PDF data
    file_stream = io.BytesIO(pdf.output())

    # Create a FileResponse to send the PDF file
    now = datetime.now().strftime("%Y-%m-%d")
    response = FileResponse(file_stream, content_type='application/pdf', filename=f"event_{event.id}_{now}.pdf")
    
    return response

def get_all_event_statistics(locations=None):
    events = Event.objects.all().order_by('start_time')

    # filter event by locations if provided
    if locations is not None:
        events = events.filter(location__in=locations)

    events_stats = []

    stat_keys = [
        'waiting',
        'presale_online_waiting',
        'presale_online',
        'presale_door',
        'door',
        'total_sold',
        'total_count',
        'activated_presale_online',
        'activated_presale_door',
        'activated_door',
        'total_activated',
        'earned_presale_online',
        'earned_presale_door',
        'earned_door',
        'total_earned',
    ]

    def _empty_stats():
        return {key: 0 for key in stat_keys}

    location_scope = locations if locations is not None else Location.objects.filter(event__isnull=False).distinct()
    per_location_stats_map = {
        location.id: {
            'location': location,
            'stats': _empty_stats(),
        }
        for location in location_scope
    }

    overall_refunded = {
        'total_refunded': 0,
        'total_amount_refunded': Decimal('0.0')
    }

    overall_total_stats = _empty_stats()

    # compute each event statistics once and accumulate per-location + overall totals in one pass
    for event in events:
        total_stats, price_class_stats = event.calculate_statistics()
        events_stats.append({
            'event': event,
            'price_class_stats': price_class_stats,
            'total_stats': total_stats
        })

        if event.location_id not in per_location_stats_map:
            per_location_stats_map[event.location_id] = {
                'location': event.location,
                'stats': _empty_stats(),
            }

        for key in stat_keys:
            value = total_stats.get(key, 0)
            overall_total_stats[key] += value
            per_location_stats_map[event.location_id]['stats'][key] += value

    per_location_stats = list(per_location_stats_map.values())

    # get refunded statistics for all orders that have been refunded; their tickets are removed by the refund/cancel logic,
    for order in get_payment_model().objects.filter(status=PaymentStatus.REFUNDED):
        overall_refunded['total_refunded'] += 1
        overall_refunded['total_amount_refunded'] += order.total

    return events_stats, per_location_stats, overall_total_stats, overall_refunded


def _get_statistics_location_scope(user, selected_location_id=None):
    location_options = Location.objects.filter(event__isnull=False).distinct().order_by('name')
    locations = None

    if is_user_in_ticket_managers_group_or_admin(user) and not is_admin_user(user):
        active_locations = get_user_active_locations(user)
        if active_locations is not None and active_locations.exists():
            location_options = active_locations.order_by('name')
            locations = active_locations
        else:
            location_options = Location.objects.none()
            locations = Location.objects.none()

    if selected_location_id:
        if locations is not None:
            locations = locations.filter(id=selected_location_id)
        else:
            locations = location_options.filter(id=selected_location_id)

    return locations, location_options

@login_required
@user_passes_test(is_user_in_ticket_managers_group_or_admin)
def all_events_statistics(request):
    selected_location_id = request.GET.get('location')
    locations, location_options = _get_statistics_location_scope(request.user, selected_location_id)
    events_stats, per_location_stats, overall_total_stats, overall_refunded = get_all_event_statistics(locations=locations)

    return render(request, 'all_event_statistics.html', {
        'events_stats': events_stats,
        'per_location_stats': per_location_stats,
        'overall_total_stats': overall_total_stats,
        'overall_refunded': overall_refunded,
        'currency': settings.DEFAULT_CURRENCY,
        'location_options': location_options,
        'selected_location_id': selected_location_id
    })


def generate_global_statistics_pdf(locations=None):
    # Generate statistics for all events
    # Create the PDF
    branding = get_active_branding()
    report_timezone = branding.timezone if branding else django_timezone.get_current_timezone()

    compact_row_specs = [
        (_('Waiting'), 'single', 'waiting'),
        (_('Presale Online Waiting'), 'single', 'presale_online_waiting'),
        (_('Presale Online (activated / sold)'), 'pair', 'activated_presale_online', 'presale_online'),
        (_('Presale Door (activated / sold)'), 'pair', 'activated_presale_door', 'presale_door'),
        (_('Door (activated / sold)'), 'pair', 'activated_door', 'door'),
        (_('Total Sold (activated / sold)'), 'pair', 'total_activated', 'total_sold'),
        (_('Total'), 'single', 'total_count'),
        (_('Total Earned Presale Online'), 'single', 'earned_presale_online'),
        (_('Total Earned Presale Door'), 'single', 'earned_presale_door'),
        (_('Total Earned Door'), 'single', 'earned_door'),
        (_('Total Earned'), 'single', 'total_earned'),
    ]

    def _format_compact_row(stats_source, row_spec):
        if row_spec[1] == 'pair':
            return f"{stats_source[row_spec[2]]} / {stats_source[row_spec[3]]}"
        key = row_spec[2]
        value = stats_source[key]
        return f"{value} {settings.DEFAULT_CURRENCY}" if 'earned' in key else f"{value}"

    pdf = FPDF(unit="cm", format=(21.0, 29.7))  # A4 format

    def _safe_pdf_text(value):
        text = str(value).translate(str.maketrans({
            '–': '-',
            '—': '-',
            '−': '-',
            '“': '"',
            '”': '"',
            '’': "'",
            '\u00a0': ' ',
            '…': '...'
        }))
        return text.encode('latin-1', errors='replace').decode('latin-1')

    original_cell = pdf.cell
    original_multi_cell = pdf.multi_cell

    def safe_cell(*args, **kwargs):
        if 'text' in kwargs:
            kwargs['text'] = _safe_pdf_text(kwargs['text'])
        return original_cell(*args, **kwargs)

    def safe_multi_cell(*args, **kwargs):
        if 'text' in kwargs:
            kwargs['text'] = _safe_pdf_text(kwargs['text'])
        return original_multi_cell(*args, **kwargs)

    pdf.cell = safe_cell
    pdf.multi_cell = safe_multi_cell

    pdf.set_margins(1.0, 1.0)
    pdf.set_auto_page_break(auto=True, margin=0.2)
    pdf.add_page()
    font = "Helvetica"
    pdf.set_font(font, size=18, style='B')
    pdf.cell(19.0, 1.0, text=_("All Events - Statistics"), border=0, align='C')
    pdf.ln(1.0)
    # created at
    created_at = django_timezone.localtime(django_timezone.now(), timezone=report_timezone)
    pdf.set_font(font, size=10)
    pdf.cell(19.0, 0.6, text=_("Created at:") + f" {created_at.strftime('%d.%m.%Y %H:%M %Z')}", border=0, align='L')
    pdf.ln(0.6)

    # add global statistics
    events_stats, per_location_stats, overall_total_stats, overall_refunded = get_all_event_statistics(locations=locations)

    pdf.set_font(font, size=12, style='B')
    pdf.cell(19.0, 0.8, text=_("Global Statistics"), border=0, align='L')
    pdf.ln(0.8)
    pdf.set_font(font, size=10)
    location_entries = per_location_stats
    statistic_column_width = 6.5
    value_column_width = (19.0 - statistic_column_width) / max(len(location_entries) + 1, 1)

    # Create table for global statistics
    pdf.set_fill_color(200, 220, 255)
    pdf.cell(statistic_column_width, 0.6, text=_("Statistic"), border=1, align='C', fill=True)
    for entry in location_entries:
        pdf.cell(value_column_width, 0.6, text=f"{entry['location'].name}", border=1, align='C', fill=True)
    pdf.cell(value_column_width, 0.6, text=_("Global"), border=1, align='C', fill=True)
    pdf.ln(0.6)
    for row_spec in compact_row_specs:
        pdf.cell(statistic_column_width, 0.6, text=row_spec[0], border=1, align='L')
        for entry in location_entries:
            location_stats = entry['stats']
            pdf.cell(value_column_width, 0.6, text=_format_compact_row(location_stats, row_spec), border=1, align='L')
        pdf.cell(value_column_width, 0.6, text=_format_compact_row(overall_total_stats, row_spec), border=1, align='L')
        pdf.ln(0.6)

    # Add refunded statistics in separate table as they are not included in the overall total statistics
    pdf.ln(1.0)
    pdf.set_font(font, size=12, style='B')
    pdf.cell(19.0, 0.8, text=_("Refunded/Canceled Orders Statistics"), border=0, align='L')
    pdf.ln(0.8)
    pdf.set_font(font, size=10)
    pdf.set_fill_color(255, 200, 200)
    pdf.cell(9.0, 0.6, text=_("Statistic"), border=1, align='C', fill=True)
    pdf.cell(10.0, 0.6, text=_("Value"), border=1, align='C', fill=True)
    pdf.ln(0.6)
    pdf.cell(9.0, 0.6, text=_("Total Refunded/Canceled Orders"), border=1, align='L')
    pdf.cell(10.0, 0.6, text=f"{overall_refunded['total_refunded']}", border=1, align='L')
    pdf.ln(0.6)
    pdf.cell(9.0, 0.6, text=_("Total Amount"), border=1, align='L')
    pdf.cell(10.0, 0.6, text=f"{overall_refunded['total_amount_refunded']} {settings.DEFAULT_CURRENCY}", border=1, align='L')
    pdf.ln(0.6)
    

    for event_stats in events_stats:
        # Add a new page for each event
        pdf.add_page()

        event = event_stats['event']

        # Fetch statistics
        total_stats = event_stats['total_stats']
        price_class_stats = event_stats['price_class_stats']

        value_column_width = (19.0 - statistic_column_width) / max(len(price_class_stats.keys()) + 1, 1)

        # Add event name
        pdf.set_font(font, size=14, style='B')
        pdf.cell(19.0, 0.8, text=f"{event.name} - { _('Statistics') }", border=0, align='L')
        pdf.ln(0.8)
        pdf.set_font(font, size=12, style='B')
        pdf.cell(4.0, 0.6, text=_("Start:"), border=0, align='L')
        pdf.cell(5.0, 0.6, text=f"{event.start_time_in_timezone.strftime('%H:%M %d.%m.%Y %Z')}", border=0, align='L')
        pdf.ln(0.8)
        pdf.cell(4.0, 0.6, text=_("Venue:"), border=0, align='L')
        pdf.cell(10.0, 0.6, text=f"{event.location.name}", border=0, align='L')
        pdf.ln(0.8)
        pdf.cell(4.0, 0.6, text=_("Capacity:"), border=0, align='L')
        pdf.cell(10.0, 0.6, text=f"{ event.remaining_seats } / { event.total_seats }", border=0, align='L')
        pdf.ln(1.0)

        # Add total statistics
        pdf.set_font(font, size=12, style='B')
        pdf.cell(19.0, 0.8, text=_("Total Statistics"), border=0, align='L')
        pdf.ln(0.8)
        pdf.set_font(font, size=10)

        # Create table for total statistics
        pdf.set_fill_color(200, 220, 255)
        pdf.cell(statistic_column_width, 0.6, text=_("Statistic"), border=1, align='C', fill=True)
        pdf.cell(value_column_width, 0.6, text=_("Value"), border=1, align='C', fill=True)
        pdf.ln(0.6)
        for row_spec in compact_row_specs:
            pdf.cell(statistic_column_width, 0.6, text=row_spec[0], border=1, align='L')
            pdf.cell(value_column_width, 0.6, text=_format_compact_row(total_stats, row_spec), border=1, align='L')
            pdf.ln(0.6)

        pdf.ln(1.0)

        # Add price class statistics
        pdf.set_font(font, size=12, style='B')
        pdf.cell(19.0, 0.8, text=_("Price Class Statistics"), border=0, align='L')
        pdf.ln(0.8)
        pdf.set_font(font, size=10)

        # Create table for price class statistics
        pdf.set_fill_color(200, 220, 255)
        pdf.cell(statistic_column_width, 1.2, text=_("Statistic"), border=1, align='C', fill=True)
        for price_class in price_class_stats.keys():
            pdf.multi_cell(value_column_width, 1.2, text=f"{price_class.name}", border=1, align='C', fill=True, ln=3, max_line_height=pdf.font_size*1.5)
        pdf.ln(1.2)
        pdf.cell(statistic_column_width, 0.6, text=_("Price"), border=1, align='C', fill=True)
        for price_class in price_class_stats.keys():
            pdf.cell(value_column_width, 0.6, text=f"{price_class.price} {settings.DEFAULT_CURRENCY}", border=1, align='C', fill=True)
        pdf.ln(0.6)
        for row_spec in compact_row_specs:
            pdf.cell(statistic_column_width, 0.6, text=row_spec[0], border=1, align='L')
            for price_class, stats in price_class_stats.items():
                pdf.cell(value_column_width, 0.6, text=_format_compact_row(stats, row_spec), border=1, align='L')
            pdf.ln(0.6)
        
    return pdf

@login_required
@user_passes_test(is_user_in_ticket_managers_group_or_admin)
def show_generated_global_statistics_pdf(request):
    selected_location_id = request.GET.get('location')
    locations, _ = _get_statistics_location_scope(request.user, selected_location_id)

    # Generate PDF for the selected ticket
    pdf = generate_global_statistics_pdf(locations=locations)
    # Create a BytesIO stream to hold
    file_stream = io.BytesIO(pdf.output())
    # Create a FileResponse to send the PDF file
    now = datetime.now().strftime("%Y-%m-%d")
    response = FileResponse(file_stream, content_type='application/pdf', filename=f"all_events_{now}.pdf")

    return response
