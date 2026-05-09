"""
Intent Classifier Interface
Uses real trained RoBERTa model for intent classification
"""

from dataclasses import dataclass
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import json
import os

@dataclass
class ClassifierOutput:
    intent: str
    category: str
    confidence: float

class IntentClassifier:
    def __init__(self, model_path: str = None):
        # Allow override via env variable, fallback to default path
        if model_path is None:
            model_path = os.getenv(
                "INTENT_CLASSIFIER_PATH",
                os.path.join(os.path.dirname(__file__), "bna_intent_classifier")
            )

        model_path = os.path.abspath(model_path)

        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Intent classifier model not found at: {model_path}\n"
                "Make sure to bna_intent_classifier/ folder is in project root."
            )

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model     = AutoModelForSequenceClassification.from_pretrained(model_path)
        self.model.to(self.device)
        self.model.eval()

        label_config_path = os.path.join(model_path, "label_config.json")
        with open(label_config_path) as f:
            config = json.load(f)

        # JSON keys are always strings — convert back to int
        self.id2label = {int(k): v for k, v in config["id2label"].items()}

        print(f"Intent classifier loaded on: {self.device}")
        print(f"Labels: {len(self.id2label)} intents")

    def classify(self, text: str) -> ClassifierOutput:
        inputs = self.tokenizer(
            text,
            return_tensors = "pt",
            truncation     = True,
            max_length     = 512,
            padding        = True,
        ).to(self.device)

        with torch.no_grad():
            logits = self.model(**inputs).logits

        probs              = torch.softmax(logits, dim=-1)
        confidence, pred_id = probs.max(dim=-1)
        intent             = self.id2label[pred_id.item()]
        category           = self._derive_category(intent)

        return ClassifierOutput(
            intent     = intent,
            category   = category,
            confidence = round(confidence.item(), 4),
        )

    def _derive_category(self, intent: str) -> str:
        loan_keywords = {
            "loan", "mortgage", "credit", "financing",
            "repay", "murabaha", "sukuk", "housing", "construction"
        }
        info_keywords = {
            "info", "procedure", "conditions", "explain",
            "understand", "advice", "information", "regulation"
        }
        for kw in loan_keywords:
            if kw in intent:
                return "loan"
        for kw in info_keywords:
            if kw in intent:
                return "information"
        return "operations"

# Singleton — imported everywhere, model loads once at startup
classifier = IntentClassifier()
