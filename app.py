import streamlit as st

# Configure page settings
st.set_page_config(
    page_title="Real Estate Advisory Panel",
    page_icon="🏘️",
    layout="wide",
)

def main():
    st.title("🏘️ Real Estate Advisory Panel")
    st.markdown("Enter your profile details in the sidebar and ask your real estate question below.")

    # 1. Create the sidebar with all specified input fields
    with st.sidebar:
        st.header("👤 User Profile")
        st.markdown("Please provide your investment preferences:")
        
        min_budget = st.number_input("Min Budget (₹)", min_value=0, value=5000000, step=100000)
        max_budget = st.number_input("Max Budget (₹)", min_value=0, value=15000000, step=100000)
        
        purpose = st.selectbox(
            "Investment Purpose", 
            ["Primary Residence", "Rental Income", "Capital Appreciation", "Holiday Home", "Flipping"]
        )
        
        risk_appetite = st.selectbox(
            "Risk Appetite", 
            ["Conservative (Low Risk)", "Moderate (Medium Risk)", "Aggressive (High Risk)"]
        )
        
        timeline = st.number_input("Timeline for Returns (months)", min_value=1, value=36, step=6)
        
        cities = st.text_input("Preferred Cities", placeholder="e.g., Pune, Mumbai, Bangalore")
        
        property_type = st.selectbox(
            "Preferred Property Type", 
            ["1-BHK Apartment", "2-BHK Apartment", "3-BHK+ Apartment", "Villa", "Plot / Land", "Commercial Space"]
        )

    # 2. Create the main panel with a text area and the "Run Advisory Panel" button
    st.subheader("💬 Ask the Advisor")
    user_query = st.text_area(
        "What is your real estate question?", 
        placeholder='e.g., "Should I buy a 2-BHK in Pune?"',
        height=150
    )

    if st.button("Run Advisory Panel", type="primary"):
        if not user_query.strip():
            st.warning("Please enter a question before running the advisory panel.")
        elif not cities.strip():
            st.warning("Please enter at least one preferred city in the sidebar.")
        else:
            # 3. Combine them into a single, detailed, and context-rich prompt
            final_prompt = f"""---
**User Profile:**
- **Budget:** ₹{min_budget:,.0f} - ₹{max_budget:,.0f}
- **Investment Purpose:** {purpose}
- **Risk Appetite:** {risk_appetite}
- **Timeline for Returns:** {timeline} months
- **Preferred Cities:** {cities}
- **Preferred Property Type:** {property_type}

**User Query:**
"{user_query}"

**Task:**
"Based on the user profile above, analyze the following query and provide a real estate investment recommendation."
---"""
            
            # 4. Display the final generated prompt on the screen
            st.success("Prompt generated successfully! Ready to be sent to the LLM.")
            
            st.subheader("Generated Prompt")
            # Using code block for better readability of the prompt structure
            st.code(final_prompt, language="markdown")

if __name__ == "__main__":
    main()
