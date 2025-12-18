from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status
from django.db.models import Count, Sum, Avg, Q
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from datetime import datetime, timedelta
from .models import Occurrence, WorkDay
from .serializers import OccurrenceSerializer, WorkDaySerializer

class OccurrenceDataView(APIView):
    """
    Endpoint ABIERTO para análisis de datos
    
    Query params disponibles:
    - employee_id: Filtrar por ID de empleado
    - occurrence_type: Filtrar por tipo (technical_issues, call_drop, Bath_room)
    - start_date: Fecha inicial formato YYYY-MM-DD
    - end_date: Fecha final formato YYYY-MM-DD
    - format: 'json' (default) o 'summary'
    
    Ejemplos:
    /api/occurrences/
    /api/occurrences/?start_date=2024-01-01&end_date=2024-12-31
    /api/occurrences/?occurrence_type=call_drop

    """
    
    permission_classes = [AllowAny]  # ABIERTO - sin autenticación
    
    def get(self, request):
        try:
            # Obtener parámetros
            employee_id = request.query_params.get('employee_id')
            occurrence_type = request.query_params.get('occurrence_type')
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')
            format_type = request.query_params.get('format', 'json')
            
            # Query base
            queryset = Occurrence.objects.select_related('employee').all()
            
            # Aplicar filtros
            if employee_id:
                queryset = queryset.filter(employee_id=employee_id)
            
            if occurrence_type:
                queryset = queryset.filter(occurrence_type=occurrence_type)
            
            if start_date:
                try:
                    start = datetime.strptime(start_date, '%Y-%m-%d').date()
                    queryset = queryset.filter(date__gte=start)
                except ValueError:
                    return Response(
                        {'error': 'start_date debe tener formato YYYY-MM-DD'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            if end_date:
                try:
                    end = datetime.strptime(end_date, '%Y-%m-%d').date()
                    queryset = queryset.filter(date__lte=end)
                except ValueError:
                    return Response(
                        {'error': 'end_date debe tener formato YYYY-MM-DD'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Retornar según formato
            if format_type == 'summary':
                data = self.get_summary(queryset)
            else:
                data = self.get_json_data(queryset)
            
            return Response(data, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def get_json_data(self, queryset):
        """Datos detallados en formato JSON"""
        serializer = OccurrenceSerializer(queryset.order_by('-date', '-start_time'), many=True)
        return {
            'count': queryset.count(),
            'data': serializer.data
        }
    
    def get_summary(self, queryset):
        """Resumen estadístico para dashboards"""
        
        # Totales generales
        total_occurrences = queryset.count()
        
        # Por tipo de ocurrencia
        by_type = list(queryset.values('occurrence_type', 'occurrence_type').annotate(
            count=Count('id'),
            total_duration_minutes=Sum('duration')
        ))
        
        # Convertir duration a minutos
        for item in by_type:
            if item['total_duration_minutes']:
                item['total_duration_minutes'] = item['total_duration_minutes'].total_seconds() / 60
        
        # Por empleado (top 20)
        by_employee = list(queryset.values(
            'employee_id',
            'employee__full_name'
        ).annotate(
            count=Count('id'),
            total_duration_minutes=Sum('duration')
        ).order_by('-count')[:20])
        
        # Convertir duration a minutos
        for item in by_employee:
            if item['total_duration_minutes']:
                item['total_duration_minutes'] = item['total_duration_minutes'].total_seconds() / 60
        
        # Tendencia diaria
        daily_trend = list(queryset.annotate(
            day=TruncDate('date')
        ).values('day').annotate(
            count=Count('id')
        ).order_by('day'))
        
        # Tendencia mensual
        monthly_trend = list(queryset.annotate(
            month=TruncMonth('date')
        ).values('month').annotate(
            count=Count('id'),
            total_duration_minutes=Sum('duration')
        ).order_by('month'))
        
        # Convertir duration a minutos
        for item in monthly_trend:
            if item['total_duration_minutes']:
                item['total_duration_minutes'] = item['total_duration_minutes'].total_seconds() / 60
        
        return {
            'total_occurrences': total_occurrences,
            'by_type': by_type,
            'by_employee': by_employee,
            'daily_trend': daily_trend,
            'monthly_trend': monthly_trend
        }

class WorkDayDataView(APIView):
    """
    Endpoint para datos de WorkDay (días laborales)
    
    Query params disponibles:
    - employee_id: Filtrar por ID de empleado
    - start_date: Fecha inicial formato YYYY-MM-DD
    - end_date: Fecha final formato YYYY-MM-DD
    - has_check_out: true/false (solo días con checkout o sin checkout)
    - format: 'json' (default), 'summary', o 'stats'
    
    Ejemplos:
    employee/api/workdays/
    employee/api/workdays/?employee_id=5
    employee/api/workdays/?start_date=2024-01-01&end_date=2024-12-31
    employee/api/workdays/?has_check_out=false  (días sin checkout)
    """
    
    permission_classes = [AllowAny]  # Cambiar después a IsAuthenticated
    
    def get(self, request):
        try:
            # Obtener parámetros
            employee_id = request.query_params.get('employee_id')
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')
            has_check_out = request.query_params.get('has_check_out')
            format_type = request.query_params.get('format', 'json')
            
            # Query base con relación al empleado
            queryset = WorkDay.objects.select_related('employee').all()
            
            # Aplicar filtros
            if employee_id:
                queryset = queryset.filter(employee_id=employee_id)
            
            if start_date:
                try:
                    start = datetime.strptime(start_date, '%Y-%m-%d').date()
                    queryset = queryset.filter(check_in__date__gte=start)
                except ValueError:
                    return Response(
                        {'error': 'start_date debe tener formato YYYY-MM-DD'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            if end_date:
                try:
                    end = datetime.strptime(end_date, '%Y-%m-%d').date()
                    queryset = queryset.filter(check_in__date__lte=end)
                except ValueError:
                    return Response(
                        {'error': 'end_date debe tener formato YYYY-MM-DD'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Filtrar por días con o sin check_out
            if has_check_out is not None:
                if has_check_out.lower() == 'true':
                    queryset = queryset.filter(check_out__isnull=False)
                elif has_check_out.lower() == 'false':
                    queryset = queryset.filter(check_out__isnull=True)
            
            # Retornar según formato solicitado
            if format_type == 'summary':
                data = self.get_summary(queryset)
            elif format_type == 'stats':
                data = self.get_statistics(queryset)
            else:
                data = self.get_json_data(queryset)
            
            return Response(data, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def get_json_data(self, queryset):
        """Datos detallados en formato JSON"""
        serializer = WorkDaySerializer(queryset.order_by('-check_in'), many=True)
        return {
            'count': queryset.count(),
            'data': serializer.data
        }
    
    def get_summary(self, queryset):
        """Resumen agregado por empleado"""
        
        # Resumen por empleado
        by_employee = list(queryset.values(
            'employee_id',
            'employee__full_name'
        ).annotate(
            total_days=Count('id'),
            total_work_hours=Sum('total_work_time'),
            total_break_hours=Sum('total_break_time'),
            total_lunch_hours=Sum('total_lunch_time'),
            avg_work_hours=Avg('total_work_time'),
            days_without_checkout=Count('id', filter=Q(check_out__isnull=True))
        ).order_by('-total_days'))
        
        # Convertir timedelta a horas decimales para facilitar análisis
        for item in by_employee:
            if item['total_work_hours']:
                item['total_work_hours'] = item['total_work_hours'].total_seconds() / 3600
            if item['total_break_hours']:
                item['total_break_hours'] = item['total_break_hours'].total_seconds() / 3600
            if item['total_lunch_hours']:
                item['total_lunch_hours'] = item['total_lunch_hours'].total_seconds() / 3600
            if item['avg_work_hours']:
                item['avg_work_hours'] = item['avg_work_hours'].total_seconds() / 3600
        
        # Tendencia diaria (días trabajados por fecha)
        daily_attendance = list(queryset.annotate(
            day=TruncDate('check_in')
        ).values('day').annotate(
            employees_count=Count('employee_id', distinct=True),
            total_checkings=Count('id')
        ).order_by('day'))
        
        # Tendencia semanal
        weekly_attendance = list(queryset.annotate(
            week=TruncWeek('check_in')
        ).values('week').annotate(
            employees_count=Count('employee_id', distinct=True),
            total_days=Count('id'),
            avg_work_hours=Avg('total_work_time')
        ).order_by('week'))
        
        for item in weekly_attendance:
            if item['avg_work_hours']:
                item['avg_work_hours'] = item['avg_work_hours'].total_seconds() / 3600
        
        # Tendencia mensual
        monthly_attendance = list(queryset.annotate(
            month=TruncMonth('check_in')
        ).values('month').annotate(
            employees_count=Count('employee_id', distinct=True),
            total_days=Count('id'),
            total_work_hours=Sum('total_work_time'),
            avg_work_hours=Avg('total_work_time')
        ).order_by('month'))
        
        for item in monthly_attendance:
            if item['total_work_hours']:
                item['total_work_hours'] = item['total_work_hours'].total_seconds() / 3600
            if item['avg_work_hours']:
                item['avg_work_hours'] = item['avg_work_hours'].total_seconds() / 3600
        
        return {
            'total_workdays': queryset.count(),
            'total_employees': queryset.values('employee_id').distinct().count(),
            'by_employee': by_employee,
            'daily_attendance': daily_attendance,
            'weekly_attendance': weekly_attendance,
            'monthly_attendance': monthly_attendance
        }
    
    def get_statistics(self, queryset):
        """Estadísticas detalladas para análisis"""
        
        # Solo días con check_out (días completos)
        complete_days = queryset.filter(check_out__isnull=False)
        
        # Estadísticas generales
        stats = complete_days.aggregate(
            total_days=Count('id'),
            avg_work_hours=Avg('total_work_time'),
            max_work_hours=Sum('total_work_time'),  # Total acumulado
            avg_break_hours=Avg('total_break_time'),
            avg_lunch_hours=Avg('total_lunch_time')
        )
        
        # Convertir a horas
        if stats['avg_work_hours']:
            stats['avg_work_hours'] = stats['avg_work_hours'].total_seconds() / 3600
        if stats['max_work_hours']:
            stats['max_work_hours'] = stats['max_work_hours'].total_seconds() / 3600
        if stats['avg_break_hours']:
            stats['avg_break_hours'] = stats['avg_break_hours'].total_seconds() / 3600
        if stats['avg_lunch_hours']:
            stats['avg_lunch_hours'] = stats['avg_lunch_hours'].total_seconds() / 3600
        
        # Días sin check_out (incompletos)
        incomplete_days = queryset.filter(check_out__isnull=True).count()
        
        # Top 10 empleados por horas trabajadas
        top_workers = list(complete_days.values(
            'employee_id',
            'employee__full_name'
        ).annotate(
            total_work_hours=Sum('total_work_time'),
            total_days=Count('id')
        ).order_by('-total_work_hours')[:10])
        
        for item in top_workers:
            if item['total_work_hours']:
                item['total_work_hours'] = item['total_work_hours'].total_seconds() / 3600
        
        # Distribución de horas trabajadas (rangos)
        # Esto es útil para gráficos de distribución en Power BI
        work_hour_distribution = []
        ranges = [
            (0, 4, '0-4 horas'),
            (4, 6, '4-6 horas'),
            (6, 8, '6-8 horas'),
            (8, 10, '8-10 horas'),
            (10, 12, '10-12 horas'),
            (12, 100, '12+ horas')
        ]
        
        for min_hours, max_hours, label in ranges:
            count = complete_days.filter(
                total_work_time__gte=timedelta(hours=min_hours),
                total_work_time__lt=timedelta(hours=max_hours)
            ).count()
            work_hour_distribution.append({
                'range': label,
                'count': count
            })
        
        return {
            'general_stats': stats,
            'incomplete_days': incomplete_days,
            'complete_days': stats['total_days'],
            'top_workers': top_workers,
            'work_hour_distribution': work_hour_distribution,
            'total_unique_employees': queryset.values('employee_id').distinct().count()
        }