# formatter.py
def classify_type(name):
    if "academy" in name.lower() or "montessori" in name.lower() or "center" in name.lower():
        return "Center"
    elif "family" in name.lower() or "home" in name.lower():
        return "Family"
    return "Unknown"

def check_msft_discount(name, msft_list):
    for provider in msft_list:
        if provider.lower() in name.lower():
            return "Yes"
    return "No"
