import requests
from bs4 import BeautifulSoup
import re

def extract_links(url):
    """
    Extract all the links with BS identifiers from a webpage.

    Parameters:
    url (str): The URL of the webpage to scrape.

    Returns:
    list: A list of tuples with the BS identifier and the corresponding link.
    """
    try:
        # Fetch the page content
        response = requests.get(url)

        # Check if the request was successful
        if response.status_code == 200:
            # Parse the HTML content
            soup = BeautifulSoup(response.content, 'html.parser')

            # Extract all the <p> tags
            p_tags = soup.find_all('p')

            # Prepare a list to store the results
            result = []

            # Loop through each <p> tag
            for p in p_tags:
                # Extract all <a> tags inside the <p> tag
                a_tags = p.find_all('a')

                # Loop through each <a> tag
                for a_tag in a_tags:
                    # Look for the BS identifier (e.g., BS01-001) in the text content of the <p> tag
                    bs_identifier_match = re.search(r'BS\d{2}-\d{3}', p.text)

                    # If we find a BS identifier and a corresponding <a> tag
                    if bs_identifier_match:
                        link = "https://batspi.com/" + a_tag['href']
                        result.append(link)

            return result
        else:
            print(f"Failed to retrieve the page. Status code: {response.status_code}")
            return []
    except Exception as e:
        print(f"An error occurred: {e}")
        return []
