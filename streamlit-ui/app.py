import streamlit as st
import requests


# For Kubernetes (inside the cluster), use service names:
CATALOG_BASE = "http://catalog-svc/api/catalog"
REVIEWS_BASE = "http://review-svc:8000/api/reviews"

#  LOCAL testing (port-forward)::
# CATALOG_BASE = "http://127.0.0.1:8085/api/catalog"
# REVIEWS_BASE = "http://127.0.0.1:8086/api/reviews"

st.set_page_config(page_title="Book Explorer", page_icon="📚")

st.title("📚 Book Explorer")
st.caption("UI build: K8S-v1")
# Init session state
if "search_results" not in st.session_state:
    st.session_state.search_results = []
if "selected_book" not in st.session_state:
    st.session_state.selected_book = None


# search form
st.header("🔍 Search for a book")

query = st.text_input("Enter book title / keyword")

if st.button("Search"):
    if not query.strip():
        st.warning("Please enter a search term.")
    else:
        try:
            url = f"{CATALOG_BASE}/search"
            params = {"q": query, "limit": 10}
            res = requests.get(url, params=params)
            res.raise_for_status()
            data = res.json()
            st.session_state.search_results = data.get("items", [])
            st.session_state.selected_book = None  # reset selection
            
            # --- FIX #1: Clear temporary review state on new search ---
            if "just_submitted_reviews" in st.session_state:
                 del st.session_state["just_submitted_reviews"]
            # --------------------------------------------------------

            st.write("DEBUG status:", res.status_code)
            st.write("DEBUG keys:", list(data.keys()))
            st.write("DEBUG items length:", len(data.get("items", [])))
        except Exception as e:
            st.error(f"Error searching books: {e}")

results = st.session_state.search_results

if results:
    st.subheader("Search results")
    
    #  labels like: "Title (Author1, Author2)"
    labels = [
        f"{item['title']} ({', '.join(item['authors'])}) [{item['id']}]"
        for item in results
    ]
    selected_label = st.radio("Select a book:", labels, key="book_radio")

    # Map back to book object (reviews())
    selected_index = labels.index(selected_label)
    newly_selected_book = results[selected_index]
    
    # --- FIX #2: Clear temporary review state on different book selection ---
    current_id = st.session_state.selected_book.get("id") if st.session_state.selected_book else None
    
    if current_id != newly_selected_book["id"]:
        # If the book changed, delete the temporary key
        if "just_submitted_reviews" in st.session_state:
            del st.session_state["just_submitted_reviews"]
   

    st.session_state.selected_book = newly_selected_book
else:
    st.info("No search results yet. Try searching for something like 'python'.")


#one book select
if st.session_state.selected_book:
    book = st.session_state.selected_book
    olid = book["id"]
    st.markdown("---")
    st.header("📖 Book details")

    #details Fetch
    try:
        details_res = requests.get(f"{CATALOG_BASE}/books/{olid}")
        if details_res.status_code == 200:
            details = details_res.json()
        else:
            details = None
    except Exception:
        details = None

    st.write(f"**Title:** {book['title']}")
    st.write(f"**Authors:** {', '.join(book['authors']) or 'Unknown'}")
    st.write(f"**First published:** {book.get('first_publish_year', 'Unknown')}")
    if details:
        desc = details.get("description") or ""
        if isinstance(desc, dict):
            desc = desc.get("value", "")
        if desc:
            st.write("**Description:**")
            st.write(desc)

    #  Reviews section 
    st.markdown("---")
    st.header("⭐ Reviews")

    #Load reviews
    try:
        rev_res = requests.get(f"{REVIEWS_BASE}/reviews", params={"bookId": olid})
        rev_res.raise_for_status()
        reviews = rev_res.json()
    except Exception as e:
        st.error(f"Error loading reviews: {e}")
        reviews = []

    if reviews:
        for r in reviews:
            st.write(f"**Rating:** {r['rating']} / 5")
            st.write(f"**Review:** {r['text']}")
            st.write(f"**User ID:** {r['userId']}")
            #st.write(f"**User Name:** {r['userName']}") 
            st.write("---")
    else:
        st.info("No reviews yet for this book. Be the first to add one!")

    # Add review 
    st.subheader("Add your review")

    user_name = st.text_input("Your name", key="rev_name")
    rating = st.slider("Rating", min_value=1, max_value=5, value=5)
    text = st.text_area("Your review", key="rev_text")

    if st.button("Submit review"):
        if not user_name.strip() or not text.strip():
            st.warning("Please enter your name and review text.")
        else:
            try:
                #  user
                user_res = requests.post(f"{REVIEWS_BASE}/users", json={"name": user_name})
                user_res.raise_for_status()
                user_id = user_res.json()["id"]

                # 2.review
                review_body = {
                    "userId": user_id,
                    "bookId": olid,
                    "rating": int(rating),
                    "text": text,
                }
                create_res = requests.post(f"{REVIEWS_BASE}/reviews", json=review_body)
                create_res.raise_for_status()

                st.success("Review submitted!")

                # Reload reviews
                rev_res = requests.get(f"{REVIEWS_BASE}/reviews", params={"bookId": olid})
                rev_res.raise_for_status()
                new_reviews = rev_res.json()
                # refreshed list
                st.session_state["just_submitted_reviews"] = new_reviews
            except Exception as e:
                st.error(f"Error submitting review: {e}")

    # refreshed reviews after submit
    if "just_submitted_reviews" in st.session_state:
        st.markdown("### Updated reviews")
        for r in st.session_state["just_submitted_reviews"]:
            st.write(f"**Rating:** {r['rating']} / 5")
            st.write(f"**Review:** {r['text']}")
            st.write(f"**User ID:** {r['userId']}")
            st.write("---")