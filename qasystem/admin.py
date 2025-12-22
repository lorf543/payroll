# admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Avg, Count
from .models import (
    QAConfig, Category, Question, Call, Evaluation, 
    QuestionResponse, EvaluationTemplate, AgentMetrics, 
    Dispute, CalibrationSession, QualityStandard
)


# ==================== INLINE MODELS ====================

class QuestionResponseInline(admin.TabularInline):
    model = QuestionResponse
    extra = 0
    readonly_fields = ('score_obtained', 'timestamp')
    fields = ('question', 'score_given', 'score_obtained', 'comments', 'evidence')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False

class QuestionInline(admin.TabularInline):
    model = Question
    extra = 1
    fields = ('text', 'category_type', 'score_type', 'weight', 'max_score', 'critical', 'is_active', 'order')
    ordering = ('order',)

# ==================== ADMIN FILTERS ====================

class ActiveFilter(admin.SimpleListFilter):
    title = 'active status'
    parameter_name = 'is_active'
    
    def lookups(self, request, model_admin):
        return (
            ('active', 'Active'),
            ('inactive', 'Inactive'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'active':
            return queryset.filter(is_active=True)
        if self.value() == 'inactive':
            return queryset.filter(is_active=False)
        return queryset

class CriticalFilter(admin.SimpleListFilter):
    title = 'critical status'
    parameter_name = 'critical'
    
    def lookups(self, request, model_admin):
        return (
            ('critical', 'Critical'),
            ('non_critical', 'Non-Critical'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'critical':
            return queryset.filter(critical=True)
        if self.value() == 'non_critical':
            return queryset.filter(critical=False)
        return queryset

class EvaluationStatusFilter(admin.SimpleListFilter):
    title = 'status'
    parameter_name = 'status'
    
    def lookups(self, request, model_admin):
        return Evaluation.EVALUATION_STATUS_CHOICES
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status=self.value())
        return queryset

class CallTypeFilter(admin.SimpleListFilter):
    title = 'call type'
    parameter_name = 'call_type'
    
    def lookups(self, request, model_admin):
        return Call.CALL_TYPE_CHOICES
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(call_type=self.value())
        return queryset

class DisputeStatusFilter(admin.SimpleListFilter):
    title = 'dispute status'
    parameter_name = 'status'
    
    def lookups(self, request, model_admin):
        return Dispute.DISPUTE_STATUS_CHOICES
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status=self.value())
        return queryset

class CalibrationStatusFilter(admin.SimpleListFilter):
    title = 'session status'
    parameter_name = 'status'
    
    def lookups(self, request, model_admin):
        return CalibrationSession.SESSION_STATUS_CHOICES
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status=self.value())
        return queryset

# ==================== MODEL ADMINS ====================

@admin.register(QAConfig)
class QAConfigAdmin(admin.ModelAdmin):
    list_display = ('name', 'max_score', 'passing_score', 'is_active_display', 'created_at')
    list_filter = (ActiveFilter,)
    fields = ('name', 'max_score', 'passing_score', 'is_active')
    actions = ['activate_config', 'deactivate_config']
    
    def is_active_display(self, obj):
        if obj.is_active:
            return format_html('<span style="color: green; font-weight: bold;">✓ Active</span>')
        return format_html('<span style="color: red;">✗ Inactive</span>')
    is_active_display.short_description = 'Status'
    
    def activate_config(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} configuration(s) activated.")
    activate_config.short_description = "Activate selected configurations"
    
    def deactivate_config(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} configuration(s) deactivated.")
    deactivate_config.short_description = "Deactivate selected configurations"

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'weight_display', 'question_count', 'is_active_display')
    list_filter = (ActiveFilter,)
    search_fields = ('name', 'description')
    fields = ('name', 'description', 'weight', 'is_active')
    inlines = [QuestionInline]
    actions = ['activate_categories', 'deactivate_categories']
    
    def weight_display(self, obj):
        return f"{obj.weight * 100:.0f}%"
    weight_display.short_description = 'Weight'
    
    def question_count(self, obj):
        count = obj.questions.count()
        url = f"/admin/qa/question/?category__id__exact={obj.id}"
        return format_html('<a href="{}">{}</a>', url, count)
    question_count.short_description = '# Questions'
    
    def is_active_display(self, obj):
        if obj.is_active:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: red;">✗</span>')
    is_active_display.short_description = 'Active'
    
    def activate_categories(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f"{queryset.count()} category(s) activated.")
    activate_categories.short_description = "Activate categories"
    
    def deactivate_categories(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f"{queryset.count()} category(s) deactivated.")
    deactivate_categories.short_description = "Deactivate categories"

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('short_text', 'category', 'category_type', 'score_type', 
                    'weight', 'max_score', 'critical_display', 'is_active_display', 'order')
    list_filter = (ActiveFilter, CriticalFilter, 'category', 'category_type', 'score_type')
    search_fields = ('text', 'category__name')
    list_editable = ('order',)
    fieldsets = (
        ('Question Details', {
            'fields': ('text', 'category', 'category_type', 'score_type')
        }),
        ('Scoring Configuration', {
            'fields': ('weight', 'max_score', 'critical')
        }),
        ('Display Settings', {
            'fields': ('is_required', 'is_active', 'order')
        }),
    )
    actions = ['activate_questions', 'deactivate_questions', 'mark_as_critical', 'mark_as_non_critical']
    
    def short_text(self, obj):
        return obj.text[:60] + "..." if len(obj.text) > 60 else obj.text
    short_text.short_description = 'Question'
    
    def critical_display(self, obj):
        if obj.critical:
            return format_html('<span style="color: red; font-weight: bold;">⚠ Critical</span>')
        return format_html('<span style="color: gray;">—</span>')
    critical_display.short_description = 'Critical'
    
    def is_active_display(self, obj):
        if obj.is_active:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: red;">✗</span>')
    is_active_display.short_description = 'Active'
    
    def activate_questions(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f"{queryset.count()} question(s) activated.")
    activate_questions.short_description = "Activate questions"
    
    def deactivate_questions(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f"{queryset.count()} question(s) deactivated.")
    deactivate_questions.short_description = "Deactivate questions"
    
    def mark_as_critical(self, request, queryset):
        queryset.update(critical=True)
        self.message_user(request, f"{queryset.count()} question(s) marked as critical.")
    mark_as_critical.short_description = "Mark as critical"
    
    def mark_as_non_critical(self, request, queryset):
        queryset.update(critical=False)
        self.message_user(request, f"{queryset.count()} question(s) marked as non-critical.")
    mark_as_non_critical.short_description = "Mark as non-critical"

@admin.register(Call)
class CallAdmin(admin.ModelAdmin):
    list_display = ('call_id', 'agent', 'call_type', 'disposition', 
                    'start_time', 'duration_display', 'evaluation_link', 'recording_link')
    list_filter = (CallTypeFilter, 'disposition', 'start_time')
    search_fields = ('call_id', 'agent__username', 'customer_id', 'phone_number')
    readonly_fields = ('duration', 'created_at')
    fieldsets = (
        ('Call Information', {
            'fields': ('call_id', 'agent', 'supervisor')
        }),
        ('Customer Details', {
            'fields': ('customer_id', 'phone_number')
        }),
        ('Call Specifications', {
            'fields': ('call_type', 'disposition', 'start_time', 'end_time', 'duration')
        }),
        ('Additional Information', {
            'fields': ('recording_url', 'notes', 'created_at')
        }),
    )
    
    def duration_display(self, obj):
        if obj.duration:
            total_seconds = int(obj.duration.total_seconds())
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            return f"{minutes}:{seconds:02d}"
        return "-"
    duration_display.short_description = 'Duration'
    
    def evaluation_link(self, obj):
        count = obj.evaluations.count()
        if count > 0:
            url = f"/admin/qa/evaluation/?call__id__exact={obj.id}"
            return format_html('<a href="{}">{} evaluation(s)</a>', url, count)
        return "-"
    evaluation_link.short_description = 'Evaluations'
    
    def recording_link(self, obj):
        if obj.recording_url:
            return format_html('<a href="{}" target="_blank" style="color: blue;">🔗 Play</a>', obj.recording_url)
        return "-"
    recording_link.short_description = 'Recording'

@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = ('id', 'agent', 'evaluator', 'status_display', 'score_display', 
                    'critical_display', 'evaluation_date', 'response_count')
    list_filter = (EvaluationStatusFilter, 'has_critical_failure', 'evaluation_date')
    search_fields = ('agent__username', 'evaluator__username', 'feedback')
    readonly_fields = ('total_score', 'max_possible_score', 'weighted_score', 
                      'has_critical_failure', 'created_at', 'updated_at')
    fieldsets = (
        ('Evaluation Information', {
            'fields': ('call', 'agent', 'evaluator', 'status')
        }),
        ('Scoring Results', {
            'fields': ('total_score', 'max_possible_score', 'weighted_score', 'has_critical_failure')
        }),
        ('Feedback & Development', {
            'fields': ('feedback', 'strengths', 'areas_for_improvement', 'agent_comments')
        }),
        ('Review Process', {
            'fields': ('reviewed_by', 'reviewed_date', 'evaluation_date')
        }),
        ('System Information', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    inlines = [QuestionResponseInline]
    actions = ['mark_as_completed', 'mark_as_reviewed', 'recalculate_scores']
    
    def status_display(self, obj):
        status_colors = {
            'draft': 'gray',
            'pending_review': 'orange',
            'reviewed': 'blue',
            'completed': 'green',
            'disputed': 'red'
        }
        color = status_colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 3px; font-size: 12px;">{}</span>',
            color, obj.get_status_display()
        )
    status_display.short_description = 'Status'
    
    def score_display(self, obj):
        if obj.weighted_score >= 80:
            color = 'green'
        elif obj.weighted_score >= 60:
            color = 'orange'
        else:
            color = 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}%</span>',
            color, round(obj.weighted_score, 1)
        )
    score_display.short_description = 'Score'
    
    def critical_display(self, obj):
        if obj.has_critical_failure:
            return format_html('<span style="color: red; font-weight: bold;">⚠</span>')
        return "-"
    critical_display.short_description = 'Critical'
    
    def response_count(self, obj):
        return obj.responses.count()
    response_count.short_description = 'Responses'
    
    def mark_as_completed(self, request, queryset):
        queryset.update(status='completed')
        self.message_user(request, f"{queryset.count()} evaluation(s) marked as completed.")
    mark_as_completed.short_description = "Mark as completed"
    
    def mark_as_reviewed(self, request, queryset):
        queryset.update(status='reviewed')
        self.message_user(request, f"{queryset.count()} evaluation(s) marked as reviewed.")
    mark_as_reviewed.short_description = "Mark as reviewed"
    
    def recalculate_scores(self, request, queryset):
        for evaluation in queryset:
            evaluation.calculate_scores()
        self.message_user(request, f"Scores recalculated for {queryset.count()} evaluation(s).")
    recalculate_scores.short_description = "Recalculate scores"

@admin.register(QuestionResponse)
class QuestionResponseAdmin(admin.ModelAdmin):
    list_display = ('evaluation_id', 'question_short', 'score_given', 'score_obtained', 
                    'percentage', 'timestamp')
    list_filter = ('question__category', 'evaluation__status')
    search_fields = ('evaluation__agent__username', 'question__text', 'comments')
    readonly_fields = ('score_obtained', 'timestamp')
    
    def evaluation_id(self, obj):
        url = f"/admin/qa/evaluation/{obj.evaluation.id}/change/"
        return format_html('<a href="{}">Evaluation #{}</a>', url, obj.evaluation.id)
    evaluation_id.short_description = 'Evaluation'
    
    def question_short(self, obj):
        return obj.question.text[:50] + "..." if len(obj.question.text) > 50 else obj.question.text
    question_short.short_description = 'Question'
    
    def percentage(self, obj):
        if obj.question.max_score > 0:
            percentage = (obj.score_given / obj.question.max_score) * 100
            color = 'green' if percentage >= 80 else 'orange' if percentage >= 60 else 'red'
            return format_html('<span style="color: {};">{:.1f}%</span>', color, percentage)
        return "N/A"
    percentage.short_description = 'Percentage'

@admin.register(EvaluationTemplate)
class EvaluationTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'question_count', 'category_count', 'is_active_display', 'created_by', 'created_at')
    list_filter = (ActiveFilter,)
    search_fields = ('name', 'description')
    filter_horizontal = ('questions', 'categories')
    fields = ('name', 'description', 'questions', 'categories', 'is_active', 'created_by')
    readonly_fields = ('created_by', 'created_at')
    
    def question_count(self, obj):
        count = obj.questions.count()
        url = f"/admin/qa/question/?templates__id__exact={obj.id}"
        return format_html('<a href="{}">{}</a>', url, count)
    question_count.short_description = '# Questions'
    
    def category_count(self, obj):
        return obj.categories.count()
    category_count.short_description = '# Categories'
    
    def is_active_display(self, obj):
        if obj.is_active:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: red;">✗</span>')
    is_active_display.short_description = 'Active'
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

@admin.register(AgentMetrics)
class AgentMetricsAdmin(admin.ModelAdmin):
    list_display = ('agent', 'total_evaluations', 'average_score_display', 'compliance_rate_display', 
                    'trend_display', 'last_evaluation_date')
    search_fields = ('agent__username', 'agent__email')
    readonly_fields = ('total_evaluations', 'average_score', 'trend', 'compliance_rate', 
                      'last_evaluation_date', 'updated_at')
    actions = ['update_metrics']
    
    def average_score_display(self, obj):
        if obj.average_score >= 80:
            color = 'green'
        elif obj.average_score >= 60:
            color = 'orange'
        else:
            color = 'red'
        return format_html('<span style="color: {}; font-weight: bold;">{}%</span>', color, round(obj.average_score, 1))
    average_score_display.short_description = 'Avg Score'
    
    def compliance_rate_display(self, obj):
        return format_html('{}%', round(obj.compliance_rate, 1))
    compliance_rate_display.short_description = 'Compliance'
    
    def trend_display(self, obj):
        if obj.trend > 0:
            return format_html('<span style="color: green;">↑ +{}%</span>', round(obj.trend, 1))
        elif obj.trend < 0:
            return format_html('<span style="color: red;">↓ {}%</span>', round(obj.trend, 1))
        return format_html('<span style="color: gray;">→ {}%</span>', round(obj.trend, 1))
    trend_display.short_description = 'Trend'
    
    def update_metrics(self, request, queryset):
        for metric in queryset:
            metric.update_metrics()
        self.message_user(request, f"Metrics updated for {queryset.count()} agent(s).")
    update_metrics.short_description = "Update metrics"

@admin.register(Dispute)
class DisputeAdmin(admin.ModelAdmin):
    list_display = ('id', 'evaluation_link', 'agent', 'status_display', 'created_at', 
                    'resolved_by', 'resolved_at')
    list_filter = (DisputeStatusFilter, 'created_at')
    search_fields = ('agent__username', 'evaluation__id', 'reason')
    readonly_fields = ('created_at', 'resolved_at')
    fieldsets = (
        ('Dispute Information', {
            'fields': ('evaluation', 'agent', 'status')
        }),
        ('Dispute Details', {
            'fields': ('reason', 'suggested_changes')
        }),
        ('Resolution', {
            'fields': ('resolved_by', 'resolution_notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'resolved_at')
        }),
    )
    actions = ['mark_as_resolved', 'mark_as_rejected', 'mark_as_under_review']
    
    def evaluation_link(self, obj):
        url = f"/admin/qa/evaluation/{obj.evaluation.id}/change/"
        return format_html('<a href="{}">Evaluation #{}</a>', url, obj.evaluation.id)
    evaluation_link.short_description = 'Evaluation'
    
    def status_display(self, obj):
        status_colors = {
            'pending': 'orange',
            'under_review': 'blue',
            'resolved': 'green',
            'rejected': 'red'
        }
        color = status_colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 3px; font-size: 12px;">{}</span>',
            color, obj.get_status_display()
        )
    status_display.short_description = 'Status'
    
    def mark_as_resolved(self, request, queryset):
        from django.utils import timezone
        queryset.update(status='resolved', resolved_by=request.user, resolved_at=timezone.now())
        self.message_user(request, f"{queryset.count()} dispute(s) marked as resolved.")
    mark_as_resolved.short_description = "Mark as resolved"
    
    def mark_as_rejected(self, request, queryset):
        from django.utils import timezone
        queryset.update(status='rejected', resolved_by=request.user, resolved_at=timezone.now())
        self.message_user(request, f"{queryset.count()} dispute(s) marked as rejected.")
    mark_as_rejected.short_description = "Mark as rejected"
    
    def mark_as_under_review(self, request, queryset):
        queryset.update(status='under_review')
        self.message_user(request, f"{queryset.count()} dispute(s) marked as under review.")
    mark_as_under_review.short_description = "Mark as under review"

@admin.register(CalibrationSession)
class CalibrationSessionAdmin(admin.ModelAdmin):
    list_display = ('name', 'scheduled_date', 'facilitator', 'status_display', 
                    'participant_count', 'evaluation_count')
    list_filter = (CalibrationStatusFilter, 'scheduled_date')
    search_fields = ('name', 'description', 'facilitator__username')
    filter_horizontal = ('participants', 'evaluations')
    fieldsets = (
        ('Session Details', {
            'fields': ('name', 'description', 'facilitator', 'status')
        }),
        ('Schedule', {
            'fields': ('scheduled_date',)
        }),
        ('Participants & Content', {
            'fields': ('participants', 'evaluations')
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
    )
    
    def status_display(self, obj):
        status_colors = {
            'scheduled': 'blue',
            'in_progress': 'orange',
            'completed': 'green',
            'cancelled': 'red'
        }
        color = status_colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 3px; font-size: 12px;">{}</span>',
            color, obj.get_status_display()
        )
    status_display.short_description = 'Status'
    
    def participant_count(self, obj):
        return obj.participants.count()
    participant_count.short_description = 'Participants'
    
    def evaluation_count(self, obj):
        return obj.evaluations.count()
    evaluation_count.short_description = 'Evaluations'

@admin.register(QualityStandard)
class QualityStandardAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'revision_number', 'effective_date', 
                    'is_active_display', 'created_by', 'created_at')
    list_filter = (ActiveFilter, 'category', 'effective_date')
    search_fields = ('name', 'description', 'requirements')
    readonly_fields = ('revision_number', 'created_by', 'created_at')
    fieldsets = (
        ('Standard Information', {
            'fields': ('name', 'category', 'description')
        }),
        ('Requirements', {
            'fields': ('requirements',)
        }),
        ('Version Control', {
            'fields': ('effective_date', 'revision_number', 'is_active')
        }),
        ('Audit Information', {
            'fields': ('created_by', 'created_at')
        }),
    )
    
    def is_active_display(self, obj):
        if obj.is_active:
            return format_html('<span style="color: green; font-weight: bold;">Active</span>')
        return format_html('<span style="color: red;">Inactive</span>')
    is_active_display.short_description = 'Status'
    
    def save_model(self, request, obj, form, change):
        if not change:  # New object
            obj.created_by = request.user
            # Auto-increment revision number
            last_rev = QualityStandard.objects.filter(
                name=obj.name
            ).order_by('-revision_number').first()
            obj.revision_number = (last_rev.revision_number + 1) if last_rev else 1
        super().save_model(request, obj, form, change)