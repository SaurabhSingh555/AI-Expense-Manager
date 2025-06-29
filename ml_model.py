from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import make_pipeline
import joblib
import os

# Sample training data
train_data = [
    ("bought groceries at walmart", "food"),
    ("dinner at olive garden", "food"),
    ("monthly rent payment", "rent"),
    ("electricity bill", "utilities"),
    ("netflix subscription", "entertainment"),
    ("uber ride to work", "transport"),
    ("gas station fill up", "transport"),
    ("movie tickets", "entertainment"),
    ("iphone purchase", "shopping"),
    ("starbucks coffee", "food"),
    ("doctor's visit", "healthcare"), # Added for more variety
    ("tuition fees", "education"),    # Added for more variety
    ("new shirt from mall", "shopping"),
    ("monthly bus pass", "transport"),
    ("internet bill", "utilities")
]

# Check if model exists, otherwise train and save it
model_path = 'expense_classifier.joblib'

if os.path.exists(model_path):
    model = joblib.load(model_path)
else:
    # Prepare training data
    descriptions = [item[0] for item in train_data]
    categories = [item[1] for item in train_data]
    
    # Create and train model
    model = make_pipeline(TfidfVectorizer(), MultinomialNB())
    model.fit(descriptions, categories)
    
    # Save model
    joblib.dump(model, model_path)

def predict_category(description):
    # Ensure the prediction always returns a title-cased category
    return model.predict([description])[0].title()