from datetime import datetime, timedelta

from django.db.models import Count, Sum, Avg, Q
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status

from .models import Occurrence, WorkDay
from .serializers import OccurrenceSerializer, WorkDaySerializer


# =====================================================
# Helpers
# =====================================================

def parse_date(value, field_name):
    """
    Convierte una fecha YYYY-MM-DD en objeto date.
    """
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        raise ValueError(f'{field_name} debe tener formato YYYY-MM-DD')


def td_to_seconds(value):
    """
    Convierte timedelta a segundos.
    """
    return int(value.total_seconds()) if value else 0


# =====================================================
# OCCURRENCES
# =====================================================

class OccurrenceDataView(APIView):
    """
    📊 OCCURRENCE DATA API (OPEN)

    Endpoint para análisis de ocurrencias.

    ─── Query params ───
    employee_id       → ID del empleado
    occurrence_type   → technical_issues | call_drop | bathroom | etc
    start_date        → YYYY-MM-DD
    end_date          → YYYY-MM-DD
    format            → json (default) | summary

    ─── Ejemplos ───
    /api/occurrences/
    /api/occurrences/?occurrence_type=call_drop
    /api/occurrences/?employee_id=3&start_date=2024-01-01&end_date=2024-12-31


    ─── Notas ───
    • Todos los tiempos están en SEGUNDOS

    """

    permission_classes = [AllowAny]

    def get(self, request):
        try:
            qs = Occurrence.objects.select_related('employee')

            if eid := request.query_params.get('employee_id'):
                qs = qs.filter(employee_id=eid)

            if otype := request.query_params.get('occurrence_type'):
                qs = qs.filter(occurrence_type=otype)

            if sd := request.query_params.get('start_date'):
                qs = qs.filter(date__gte=parse_date(sd, 'start_date'))

            if ed := request.query_params.get('end_date'):
                qs = qs.filter(date__lte=parse_date(ed, 'end_date'))

            if request.query_params.get('format') == 'summary':
                return Response(self.summary(qs))

            return Response(self.json_data(qs))

        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def json_data(self, qs):
        """
        Retorna datos crudos de ocurrencias.
        """
        return {
            'count': qs.count(),
            'data': OccurrenceSerializer(
                qs.order_by('-date', '-start_time'), many=True
            ).data
        }

    def summary(self, qs):
        """
        Retorna métricas agregadas para dashboards.
        """
        by_type = qs.values('occurrence_type').annotate(
            count=Count('id'),
            duration=Sum('duration')
        )

        by_employee = qs.values(
            'employee_id', 'employee__full_name'
        ).annotate(
            count=Count('id'),
            duration=Sum('duration')
        ).order_by('-count')[:20]

        daily = qs.annotate(
            day=TruncDate('date')
        ).values('day').annotate(count=Count('id')).order_by('day')

        monthly = qs.annotate(
            month=TruncMonth('date')
        ).values('month').annotate(
            count=Count('id'),
            duration=Sum('duration')
        ).order_by('month')

        return {
            'total_occurrences': qs.count(),
            'by_type': [
                {
                    'occurrence_type': x['occurrence_type'],
                    'count': x['count'],
                    'duration_seconds': td_to_seconds(x['duration']),
                } for x in by_type
            ],
            'by_employee': [
                {
                    'employee_id': x['employee_id'],
                    'employee': x['employee__full_name'],
                    'count': x['count'],
                    'duration_seconds': td_to_seconds(x['duration']),
                } for x in by_employee
            ],
            'daily_trend': list(daily),
            'monthly_trend': [
                {
                    'month': x['month'],
                    'count': x['count'],
                    'duration_seconds': td_to_seconds(x['duration']),
                } for x in monthly
            ]
        }


# =====================================================
# WORKDAYS
# =====================================================

class WorkDayDataView(APIView):
    """
    📅 WORKDAY DATA API (OPEN)

    Endpoint para análisis de jornadas laborales.

    ─── Query params ───
    employee_id    → ID del empleado
    start_date     → YYYY-MM-DD
    end_date       → YYYY-MM-DD
    has_check_out  → true | false
    format         → json (default) | summary | stats

    ─── Ejemplos ───
    /api/workdays/
    /api/workdays/?employee_id=8
    /api/workdays/?has_check_out=false
    /api/workdays/?format=stats

    ─── Notas ───
    • Todos los tiempos están en SEGUNDOS

    """

    permission_classes = [AllowAny]

    def get(self, request):
        try:
            qs = WorkDay.objects.select_related('employee')

            if eid := request.query_params.get('employee_id'):
                qs = qs.filter(employee_id=eid)

            if sd := request.query_params.get('start_date'):
                qs = qs.filter(check_in__date__gte=parse_date(sd, 'start_date'))

            if ed := request.query_params.get('end_date'):
                qs = qs.filter(check_in__date__lte=parse_date(ed, 'end_date'))

            if hc := request.query_params.get('has_check_out'):
                qs = qs.filter(check_out__isnull=hc.lower() == 'false')

            fmt = request.query_params.get('format', 'json')

            if fmt == 'summary':
                return Response(self.summary(qs))

            if fmt == 'stats':
                return Response(self.stats(qs))

            return Response(self.json_data(qs))

        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def json_data(self, qs):
        """
        Retorna jornadas individuales.
        """
        return {
            'count': qs.count(),
            'data': WorkDaySerializer(
                qs.order_by('-check_in'), many=True
            ).data
        }

    def summary(self, qs):
        """
        Resumen agregado por empleado y tiempo.
        """
        by_employee = qs.values(
            'employee_id', 'employee__full_name'
        ).annotate(
            total_days=Count('id'),
            work=Sum('total_work_time'),
            breaks=Sum('total_break_time'),
            lunch=Sum('total_lunch_time'),
            avg_work=Avg('total_work_time'),
            no_checkout=Count('id', filter=Q(check_out__isnull=True))
        )

        return {
            'total_workdays': qs.count(),
            'total_employees': qs.values('employee_id').distinct().count(),
            'by_employee': [
                {
                    'employee_id': x['employee_id'],
                    'employee': x['employee__full_name'],
                    'total_days': x['total_days'],
                    'work_seconds': td_to_seconds(x['work']),
                    'break_seconds': td_to_seconds(x['breaks']),
                    'lunch_seconds': td_to_seconds(x['lunch']),
                    'avg_work_seconds': td_to_seconds(x['avg_work']),
                    'days_without_checkout': x['no_checkout'],
                } for x in by_employee
            ]
        }

    def stats(self, qs):
        """
        Estadísticas avanzadas para BI.
        """
        complete = qs.filter(check_out__isnull=False)

        stats = complete.aggregate(
            total_days=Count('id'),
            total_work=Sum('total_work_time'),
            avg_work=Avg('total_work_time'),
            avg_break=Avg('total_break_time'),
            avg_lunch=Avg('total_lunch_time'),
        )

        return {
            'general': {
                'total_days': stats['total_days'],
                'total_work_seconds': td_to_seconds(stats['total_work']),
                'avg_work_seconds': td_to_seconds(stats['avg_work']),
                'avg_break_seconds': td_to_seconds(stats['avg_break']),
                'avg_lunch_seconds': td_to_seconds(stats['avg_lunch']),
            },
            'incomplete_days': qs.filter(check_out__isnull=True).count(),
            'total_unique_employees': qs.values('employee_id').distinct().count()
        }
