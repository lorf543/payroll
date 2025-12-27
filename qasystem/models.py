from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone

# Create your models here.

class QAConfig(models.Model):
    """General QA System Configuration"""
    name = models.CharField(max_length=100)
    max_score = models.DecimalField(max_digits=5, decimal_places=2, default=100.00)
    passing_score = models.DecimalField(max_digits=5, decimal_places=2, default=80.00)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True,null=True)
    weight = models.DecimalField(max_digits=5, decimal_places=2, default=1.0, 
                                 validators=[MinValueValidator(0), MaxValueValidator(1)])
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name 
    
    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['name']

class Question(models.Model): 
    CATEGORY_TYPE_CHOICES = [
        ('call_handling', 'Call Handling'),
        ('technical', 'Technical/Product'),
        ('compliance', 'Compliance'),
        ('soft_skills', 'Soft Skills'),
        ('customer_service', 'Customer Service'),
    ]
    
    SCORE_TYPE_CHOICES = [
        ('binary', 'Binary (Yes/No)'),
        ('scale', 'Scale (1-5)'),
        ('percentage', 'Percentage (0-100)'),
        ('custom', 'Custom'),
    ]
    
    text = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='questions')
    category_type = models.CharField(max_length=50, choices=CATEGORY_TYPE_CHOICES, default='call_handling')
    score_type = models.CharField(max_length=20, choices=SCORE_TYPE_CHOICES, default='scale')
    weight = models.DecimalField(max_digits=5, decimal_places=2, default=1.0)
    max_score = models.DecimalField(max_digits=5, decimal_places=2, default=5.0)
    is_required = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    critical = models.BooleanField(default=False, help_text="Critical failure affects final score")
    
    def __str__(self):
        return self.text[:50] + "..." if len(self.text) > 50 else self.text
    
    class Meta:
        ordering = ['order', 'id']

class Call(models.Model):
    """Call record being evaluated"""
    CALL_TYPE_CHOICES = [
        ('inbound', 'Inbound'),
        ('outbound', 'Outbound'),
        ('callback', 'Callback'),
        ('transfer', 'Transfer'),
    ]
    
    CALL_DISPOSITION_CHOICES = [
        ('resolved', 'Resolved'),
        ('pending', 'Pending'),
        ('escalated', 'Escalated'),
        ('abandoned', 'Abandoned'),
    ]
    
    call_id = models.CharField(max_length=100, unique=True, help_text="Unique call identifier")
    agent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, 
                              related_name='calls_evaluated')
    supervisor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, 
                                   null=True, blank=True, related_name='calls_supervised')
    customer_id = models.CharField(max_length=100, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    call_type = models.CharField(max_length=20, choices=CALL_TYPE_CHOICES, default='inbound')
    disposition = models.CharField(max_length=20, choices=CALL_DISPOSITION_CHOICES, default='resolved')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    duration = models.DurationField(help_text="Call duration")
    recording_url = models.URLField(max_length=500, blank=True, null=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Call {self.call_id} - Agent: {self.agent}"
    
    class Meta:
        ordering = ['-start_time']

class Evaluation(models.Model):
    """Complete call evaluation"""
    EVALUATION_STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending_review', 'Pending Review'),
        ('reviewed', 'Reviewed'),
        ('completed', 'Completed'),
        ('disputed', 'Disputed'),
    ]
    
    call = models.ForeignKey(Call, on_delete=models.CASCADE, related_name='evaluations')
    evaluator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, 
                                  null=True, related_name='evaluations_made')
    agent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, 
                              related_name='evaluations_received')
    status = models.CharField(max_length=20, choices=EVALUATION_STATUS_CHOICES, default='draft')
    total_score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    max_possible_score = models.DecimalField(max_digits=5, decimal_places=2, default=100.00)
    weighted_score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    has_critical_failure = models.BooleanField(default=False)
    feedback = models.TextField(blank=True)
    strengths = models.TextField(blank=True)
    areas_for_improvement = models.TextField(blank=True)
    agent_comments = models.TextField(blank=True, help_text="Agent comments about the evaluation")
    evaluation_date = models.DateTimeField(default=timezone.now)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, 
                                    null=True, blank=True, related_name='evaluations_reviewed')
    reviewed_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def calculate_scores(self):
        """Calculate scores based on responses"""
        responses = self.responses.all()
        
        if not responses:
            return
        
        total_score = 0
        total_weight = 0
        max_possible = 0
        critical_failure = False
        
        for response in responses:
            if response.question.is_active:
                total_score += response.score_obtained
                max_possible += response.question.max_score
                total_weight += response.question.weight
                if response.question.critical and response.score_obtained == 0:
                    critical_failure = True
        
        self.total_score = total_score
        self.max_possible_score = max_possible
        self.has_critical_failure = critical_failure
        
        if max_possible > 0:
            self.weighted_score = (total_score / max_possible) * 100
        
        self.save()
    
    def __str__(self):
        return f'Evaluation #{self.id} - Agent: {self.agent} - Score: {self.weighted_score}%'
    
    class Meta:
        ordering = ['-evaluation_date']
        verbose_name_plural = "Evaluations"

class QuestionResponse(models.Model):
    """Individual response to a question in an evaluation"""
    evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, related_name='responses')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='responses')
    score_given = models.DecimalField(max_digits=5, decimal_places=2, 
                                     validators=[MinValueValidator(0)])
    score_obtained = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    comments = models.TextField(blank=True)
    evidence = models.TextField(blank=True, help_text="Specific evidence or example from the call")
    timestamp = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        # Calculate obtained score based on question weight
        if self.score_given > self.question.max_score:
            self.score_given = self.question.max_score
        
        self.score_obtained = (self.score_given / self.question.max_score) * self.question.weight * 100
        
        super().save(*args, **kwargs)
        # Recalculate the complete evaluation
        self.evaluation.calculate_scores()
    
    def __str__(self):
        return f'Response: {self.question.text[:30]} - Score: {self.score_given}'
    
    class Meta:
        unique_together = ['evaluation', 'question']
        ordering = ['question__order']

class EvaluationTemplate(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    questions = models.ManyToManyField(Question, related_name='templates')
    categories = models.ManyToManyField(Category, related_name='templates')
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name

class AgentMetrics(models.Model):
    """Accumulated agent metrics"""
    agent = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, 
                                 related_name='qa_metrics')
    total_evaluations = models.PositiveIntegerField(default=0)
    average_score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    trend = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, 
                               help_text="Trend (positive/negative)")
    last_evaluation_date = models.DateTimeField(null=True, blank=True)
    total_calls_evaluated = models.PositiveIntegerField(default=0)
    compliance_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    updated_at = models.DateTimeField(auto_now=True)
    
    def update_metrics(self):
        evaluations = Evaluation.objects.filter(agent=self.agent, status='completed')
        self.total_evaluations = evaluations.count()
        
        if self.total_evaluations > 0:
            avg_score = evaluations.aggregate(models.Avg('weighted_score'))['weighted_score__avg']
            self.average_score = avg_score or 0.00
            
            # Calculate compliance rate (evaluations with score >= 80%)
            passing = evaluations.filter(weighted_score__gte=80).count()
            self.compliance_rate = (passing / self.total_evaluations) * 100 if self.total_evaluations > 0 else 0
            
            last_eval = evaluations.order_by('-evaluation_date').first()
            if last_eval:
                self.last_evaluation_date = last_eval.evaluation_date
        
        self.save()
    
    def __str__(self):
        return f'Metrics for {self.agent} - Average: {self.average_score}%'

class Dispute(models.Model):
    """Evaluation dispute filed by agent"""
    DISPUTE_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('under_review', 'Under Review'),
        ('resolved', 'Resolved'),
        ('rejected', 'Rejected'),
    ]
    
    evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, related_name='disputes')
    agent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, 
                              related_name='disputes_filed')
    reason = models.TextField()
    suggested_changes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=DISPUTE_STATUS_CHOICES, default='pending')
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, 
                                    null=True, blank=True, related_name='disputes_resolved')
    resolution_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f'Dispute #{self.id} - Evaluation: {self.evaluation.id}'
    
    class Meta:
        ordering = ['-created_at']

class CalibrationSession(models.Model):
    """QA calibration sessions"""
    SESSION_STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    scheduled_date = models.DateTimeField()
    facilitator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='calibrations_facilitated')
    participants = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='calibrations_attended')
    evaluations = models.ManyToManyField(Evaluation, related_name='calibration_sessions')
    status = models.CharField(max_length=20, choices=SESSION_STATUS_CHOICES, default='scheduled')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f'Calibration: {self.name} - {self.scheduled_date.date()}'

class QualityStandard(models.Model):
    """Quality standards and guidelines"""
    name = models.CharField(max_length=200)
    description = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='standards')
    requirements = models.TextField(help_text="Specific requirements for this standard")
    effective_date = models.DateField()
    revision_number = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f'{self.name} (Rev. {self.revision_number})'