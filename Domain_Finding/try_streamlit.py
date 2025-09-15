import streamlit as st
import requests
import tldextract
import time
import os
from dotenv import load_dotenv
from collections import Counter
import openai

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize OpenAI
if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY
else:
    openai = None

# Search Google Custom Search for a query and return links
def search_google(query, num=10):
    try:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            'q': query,
            'key': GOOGLE_API_KEY,
            'cx': GOOGLE_CSE_ID,
            'num': min(num, 10)  # Google CSE allows max 10 results per request
        }
        
        res = requests.get(url, params=params)
        if res.ok:
            return [item['link'] for item in res.json().get('items', [])]
        return []
    except Exception as e:
        print(f"Error searching Google: {e}")
        return []

# Extract root domains from links
def extract_root_domains(links):
    roots = []
    for link in links:
        ext = tldextract.extract(link)
        if ext.domain and ext.suffix:
            roots.append(ext.domain.lower())
    return roots

# Extract all www.<root>.* domains and return full URLs
def get_all_domains(root):
    found_domains = set()
    excluded_tlds = set(["com"])
    found_domains.add(f"https://www.{root}.com")
    while True:
        query = f"site:www.{root}.*" + (" " + " ".join(f"-{tld}" for tld in sorted(excluded_tlds)) if excluded_tlds else "")
        links = search_google(query, num=40)
        if not links:
            break
        for link in links:
            ext = tldextract.extract(link)
            if ext.domain.lower() == root and ext.suffix:
                url = f"https://www.{ext.domain.lower()}.{ext.suffix.lower()}"
                found_domains.add(url)
                excluded_tlds.add(ext.suffix.lower())
        time.sleep(1)
    return sorted(found_domains)

# Batch filter function using OpenAI for social media and news domains only
@st.cache_data(show_spinner=False)
def filter_social_and_news_domains_llm(domains):
    if not openai or not domains:
        return domains  # If OpenAI not configured, don't filter
    
    prompt = (
        "Given the following list of domain names, return ONLY the ones that are "
        "social media websites, news websites, online encyclopedias (like Wikipedia), "
        "search engines (like Google), or any general public knowledge directories. "
        "Reply with a comma-separated list of the root domains only, no explanation.\n\n"
        f"Domains: {', '.join([d + '.com' for d in domains])}"
    )
    
    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini-2024-07-18",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that filters domain names."},
                {"role": "user", "content": prompt}
            ]
        )
        
        answer = response.choices[0].message.content.strip().lower()
        print(f"OpenAI batch response: {answer}")
        flagged_domains = [d.strip().replace('.com', '') for d in answer.split(',') if d.strip()]
        return [d for d in domains if d not in flagged_domains]
    except Exception as e:
        print(f"OpenAI batch error: {e}")
        return domains

def main():
    st.title("Company Domain Finder")
    st.write("Enter a company name to find all its domains using Google.")
    company = st.text_input("Enter the company name:")
    if 'root_selected' not in st.session_state:
        st.session_state['root_selected'] = None
    if st.button("Search for Root Domains"):
        if not company:
            st.warning("Please enter a company name.")
        else:
            with st.spinner("Searching for likely root domains..."):
                links = search_google(company, num=40)
                roots = extract_root_domains(links)
                if not roots:
                    st.warning("No root domains found in search results.")
                else:
                    root_counts = Counter(roots)
                    most_common = [r for r, _ in root_counts.most_common()]
                    # LLM filtering: social media and news
                    with st.spinner("Filtering out social media and news domains"):
                        filtered_roots = filter_social_and_news_domains_llm(most_common)
                    if not filtered_roots:
                        st.warning("All found root domains are social media/news or none found.")
                    else:
                        st.session_state['root_options'] = filtered_roots
                        st.session_state['root_selected'] = None
    if 'root_options' in st.session_state and st.session_state['root_options']:
        st.write("Select the root domain to search for all www.<root>.* domains:")
        root = st.selectbox("Root domain", st.session_state['root_options'], key='root_select')
        if st.button("Find All Domains for Root Domain"):
            with st.spinner(f"Searching for all www.{root}.* domains..."):
                domains = get_all_domains(root)
            st.subheader(f"All www.{root}.* domains:")
            if domains:
                for d in domains:
                    st.write(d)
            else:
                st.write("No domains found.")

if __name__ == "__main__":
    main() 