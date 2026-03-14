import pandas as pd
import joblib
import os
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report

# Load dataset
df = pd.read_csv("fake_job_postings.csv")

# Fill missing values
df.fillna("", inplace=True)

# Combine important text fields
df["text"] = (
    df["title"] + " " +
    df["description"] + " " +
    df["requirements"] + " " +
    df["company_profile"]
)

# Define input and output
X = df["text"]
y = df["fraudulent"]

print(df[["text", "fraudulent"]].head())

titles = df["title"]

#Split data
X_train, X_test, y_train, y_test, title_train, title_test = train_test_split(
    X, y, titles, test_size=0.2, random_state=42
)


print("Training samples:", len(X_train))
print("Testing samples:", len(X_test))

# Create TF-IDF Vectorizer
tfidf = TfidfVectorizer(
    stop_words="english",
    max_features=5000
)

# Transform text
X_train_tfidf = tfidf.fit_transform(X_train)
X_test_tfidf = tfidf.transform(X_test)

print("TF-IDF shape:", X_train_tfidf.shape)

#Train Model
model = LogisticRegression(max_iter=1000,class_weight="balanced")
model.fit(X_train_tfidf, y_train)

print("Model trained successfully")

def risk_label(score):
    if score < 0.3:
        return "LOW RISK"
    elif score < 0.6:
        return "MEDIUM RISK"
    else:
        return "HIGH RISK"
    
# Predict
y_pred = model.predict(X_test_tfidf)

# Accuracy
accuracy = accuracy_score(y_test, y_pred)
print("Accuracy:", accuracy)

# Detailed report
print(classification_report(y_test, y_pred))

# Get probability scores
y_prob = model.predict_proba(X_test_tfidf)

# Probability of FAKE job (class 1)
fake_risk_scores = y_prob[:, 1]

# Show first 10 risk scores with risk level
for i in range(10):
    print("--------------------------------------------------")
    print("Job Title:", title_test.iloc[i])
    print("Risk Score:", round(fake_risk_scores[i], 3))
    print("Risk Level:", risk_label(fake_risk_scores[i]))
    print("Actual Label:", y_test.iloc[i])


THRESHOLD = 0.3

y_pred_custom = (fake_risk_scores >= THRESHOLD).astype(int)

print("Threshold:", THRESHOLD)
print(classification_report(y_test, y_pred_custom))

# Save model and vectorizer
os.makedirs("models", exist_ok=True)

joblib.dump(model, "models/fake_job_model.pkl")
joblib.dump(tfidf, "models/tfidf_vectorizer.pkl")

print("Model and vectorizer saved")