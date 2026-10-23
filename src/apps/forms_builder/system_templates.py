"""Prebuilt templates created by `manage.py bootstrap` (plain-language questions)."""


def _opts(*pairs):
    return [{"value": v, "label": en, "label_es": es} for v, en, es in pairs]


GENERAL_INTAKE = {
    "name": "General Intake",
    "description": "Short intake for any referral: what help is needed and how urgent it is.",
    "fields": [
        {
            "key": "help_needed",
            "type": "multiple_choice",
            "required": True,
            "label": "What kind of help is needed?",
            "label_es": "¿Qué tipo de ayuda necesita?",
            "options": _opts(
                ("food", "Food", "Comida"),
                ("housing", "Housing", "Vivienda"),
                ("transportation", "Transportation", "Transporte"),
                ("utilities", "Utility bills", "Facturas de servicios"),
                ("health", "Health care or medicine", "Atención médica o medicinas"),
                (
                    "mental_health",
                    "Mental health or substance use support",
                    "Salud mental o apoyo por uso de sustancias",
                ),
                ("other", "Something else", "Otra cosa"),
            ),
            "need_tag": "",
            "need_values": [],
        },
        {
            "key": "help_other",
            "type": "short_text",
            "required": True,
            "label": "Please describe what else is needed",
            "label_es": "Describa qué más necesita",
            "show_if": {"field": "help_needed", "equals": "other"},
        },
        {
            "key": "urgency",
            "type": "single_choice",
            "required": True,
            "label": "How soon is help needed?",
            "label_es": "¿Qué tan pronto necesita ayuda?",
            "options": _opts(
                ("today", "Today — it's urgent", "Hoy — es urgente"),
                ("week", "This week", "Esta semana"),
                ("later", "In the next few weeks", "En las próximas semanas"),
            ),
        },
        {
            "key": "best_time",
            "type": "single_choice",
            "required": False,
            "label": "Best time to call",
            "label_es": "Mejor hora para llamar",
            "options": _opts(
                ("morning", "Morning", "Mañana"),
                ("afternoon", "Afternoon", "Tarde"),
                ("evening", "Evening", "Noche"),
            ),
        },
        {
            "key": "notes",
            "type": "long_text",
            "required": False,
            "label": "Anything else we should know?",
            "label_es": "¿Algo más que debamos saber?",
        },
    ],
}

SDOH_SCREENING = {
    "name": "SDoH Screening",
    "description": "Social needs screening: housing, food, transportation, utilities and safety.",
    "fields": [
        {
            "key": "housing_worry",
            "type": "yes_no",
            "required": True,
            "need_tag": "HOUSING",
            "need_values": ["yes"],
            "label": "Are you worried about losing your housing, or do you not have a steady "
            "place to live?",
            "label_es": "¿Le preocupa perder su vivienda o no tiene un lugar estable donde vivir?",
        },
        {
            "key": "food_worry",
            "type": "yes_no",
            "required": True,
            "need_tag": "FOOD",
            "need_values": ["yes"],
            "label": "In the past 12 months, did you worry your food would run out before you "
            "had money to buy more?",
            "label_es": "En los últimos 12 meses, ¿le preocupó que se acabara la comida antes de "
            "tener dinero para comprar más?",
        },
        {
            "key": "transportation",
            "type": "yes_no",
            "required": True,
            "need_tag": "TRANSPORTATION",
            "need_values": ["yes"],
            "label": "Has a lack of transportation kept you from medical appointments, work, or "
            "getting things you need?",
            "label_es": "¿La falta de transporte le ha impedido ir a citas médicas, al trabajo o "
            "conseguir lo que necesita?",
        },
        {
            "key": "utilities",
            "type": "yes_no",
            "required": True,
            "need_tag": "UTILITIES",
            "need_values": ["yes"],
            "label": "In the past 12 months, has your electric, gas, oil or water company "
            "threatened to shut off service?",
            "label_es": "En los últimos 12 meses, ¿la compañía de luz, gas, aceite o agua amenazó "
            "con cortarle el servicio?",
        },
        {
            "key": "safety",
            "type": "yes_no",
            "required": True,
            "need_tag": "SAFETY",
            "need_values": ["yes"],
            "label": "Do you ever feel unsafe where you live?",
            "label_es": "¿Alguna vez se siente inseguro/a donde vive?",
        },
        {
            "key": "safety_now",
            "type": "yes_no",
            "required": False,
            "show_if": {"field": "safety", "equals": "yes"},
            "label": "Are you in danger right now? (If so, please call 911.)",
            "label_es": "¿Está en peligro ahora mismo? (Si es así, llame al 911.)",
        },
        {
            "key": "wants_help",
            "type": "multiple_choice",
            "required": False,
            "label": "Which would you like help with?",
            "label_es": "¿Con qué le gustaría recibir ayuda?",
            "options": _opts(
                ("housing", "Housing", "Vivienda"),
                ("food", "Food", "Comida"),
                ("transportation", "Transportation", "Transporte"),
                ("utilities", "Utilities", "Servicios públicos"),
                ("safety", "Safety", "Seguridad"),
            ),
        },
    ],
}

SYSTEM_TEMPLATES = [GENERAL_INTAKE, SDOH_SCREENING]
