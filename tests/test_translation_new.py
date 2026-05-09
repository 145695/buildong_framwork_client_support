import logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')

from app.layer2.shared.model_loader import get_nemotron_model

print('=== Testing French Translation ===')
nemotron = get_nemotron_model()
result = nemotron.translate_text('bonjour je souhaite obtenir un prêt hypothécaire', 'fr')
print('French Translation result:', result)

print('\n=== Testing Arabic Translation ===')
result = nemotron.translate_text('مرحبا، أريد الحصول على قرض عقاري', 'ar')
print('Arabic Translation result:', result)
