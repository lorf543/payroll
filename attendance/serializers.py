# serializers.py
from rest_framework import serializers
from .models import Occurrence, WorkDay

class OccurrenceSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    occurrence_type_display = serializers.CharField(source='get_occurrence_type_display', read_only=True)
    duration_minutes = serializers.SerializerMethodField()
    
    class Meta:
        model = Occurrence
        fields = [
            'id', 
            'employee', 
            'employee_name',
            'occurrence_type',
            'occurrence_type_display',
            'date',
            'start_time',
            'end_time',
            'duration',
            'duration_minutes',
            'comment',
            'created_at'
        ]
    
    def get_duration_minutes(self, obj):
        """Convertir duración a minutos para facilitar análisis"""
        if obj.duration:
            return obj.duration.total_seconds() / 60
        return None
    
class WorkDaySerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True) 
    class Meta:
        model = WorkDay
        fields = [
            'id',
            'employee',
            'employee_name',
            'check_in',
            'check_out',
            'total_work_time',
            'total_break_time',
            'total_lunch_time',
        ]   


