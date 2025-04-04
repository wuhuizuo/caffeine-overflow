import nltk
import ssl

try:
    # Try to create an unverified SSL context (has security risks, only for downloads)
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    # For older Python versions that may not have _create_unverified_context
    pass
else:
    # Apply the unverified context
    ssl._create_default_https_context = _create_unverified_https_context

print("Attempting to download NLTK 'punkt' package...")
try:
    nltk.download('punkt')
    nltk.download('punkt_tab')
    nltk.download('all')
    print("NLTK 'punkt' downloaded successfully!")
except Exception as e:
    print(f"Error downloading NLTK 'punkt': {e}")
    print("Please check your network connection and firewall settings.")

# Note: After downloading, theoretically ssl._create_default_https_context
# should be restored, but to be safe, it's recommended to run this download
# script only once before running your main script.