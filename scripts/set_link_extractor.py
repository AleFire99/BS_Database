import requests
from bs4 import BeautifulSoup

# Function to extract URLs from the page
def extract_urls(url, output_filename="output.txt"):
    try:
        # Fetch the page content
        response = requests.get(url)
        response.encoding = "utf-8"

        # Check if the request was successful
        if response.status_code == 200:
            # Parse the HTML content
            soup = BeautifulSoup(response.text, 'html.parser')

            # Find the <h3 id="content_1_1"> element
            h3_tag = soup.find("h3", id="content_1_1")

            if h3_tag:
                # Find all the <ul class="list1 list-indent1"> elements after the <h3> tag
                ul_tags = h3_tag.find_all_next("ul", class_="list1 list-indent1")

                # Open a file to save the URLs
                with open(output_filename, "w", encoding="utf-8") as file:
                    # Loop through each <ul> tag and extract the URLs
                    for ul_tag in ul_tags:
                        # Find all <a> tags within each <ul>
                        a_tags = ul_tag.find_all("a", href=True)
                        for a_tag in a_tags:
                            # Extract the URL and save it in the text file
                            url_to_save = a_tag["href"]
                            file.write(url_to_save + "\n")

                print(f"URLs successfully saved to {output_filename}")
            else:
                print("Error: Could not find the <h3 id='content_1_1'> element.")
        else:
            print(f"Failed to retrieve the page. Status code: {response.status_code}")

    except Exception as e:
        print(f"An error occurred: {e}")

# Example usage
url = "https://batspi.com/index.php?カードリスト"
extract_urls(url, "extracted_urls.txt")
