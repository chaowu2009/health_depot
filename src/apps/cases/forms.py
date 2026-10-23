from django import forms

from apps.core.forms import StyledFormMixin

from .models import CarePlanGoal, Case, CaseDocument, CaseNote, CaseTask
from .services import DISCHARGE_OUTCOMES, DISCHARGE_REASONS


class NewCaseForm(StyledFormMixin, forms.Form):
    client = forms.ModelChoiceField(queryset=None)
    program = forms.ModelChoiceField(queryset=None)
    case_manager = forms.ModelChoiceField(queryset=None, required=False)

    def __init__(self, *args, clients, programs, managers, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["client"].queryset = clients  # type: ignore[attr-defined]
        self.fields["program"].queryset = programs  # type: ignore[attr-defined]
        self.fields["case_manager"].queryset = managers  # type: ignore[attr-defined]


class GoalForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = CarePlanGoal
        fields = ["description", "target_date"]
        widgets = {
            "description": forms.TextInput(),
            "target_date": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {"description": "Goal"}


class TaskForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = CaseTask
        fields = ["title", "assigned_to", "due_date", "priority"]
        widgets = {"due_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, staff=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = staff  # type: ignore[attr-defined]


class NoteForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = CaseNote
        fields = ["note_type", "contact_date", "body"]
        widgets = {
            "contact_date": forms.DateInput(attrs={"type": "date"}),
            "body": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {"body": "Note"}


class DocumentForm(StyledFormMixin, forms.Form):
    file = forms.FileField(help_text="PDF, Word, PNG or JPEG — up to 10 MB.")
    document_type = forms.ChoiceField(choices=CaseDocument.DocumentType.choices)


class DischargeForm(StyledFormMixin, forms.Form):
    reason = forms.ChoiceField(choices=DISCHARGE_REASONS, label="Discharge reason")
    outcome = forms.ChoiceField(choices=DISCHARGE_OUTCOMES)
    notes = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}), required=False, max_length=4000
    )


class CaseStatusForm(forms.Form):
    status = forms.ChoiceField(choices=[c for c in Case.Status.choices if c[0] != "DISCHARGED"])
