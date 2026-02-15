"""Reusable CSS snippets for Streamlit (Sentora convention)."""

import streamlit as st


def inject_number_input_css():
    """Stack number input +/- buttons vertically to save horizontal space."""
    st.markdown(
        """<style>
    div:has(> [data-testid="stNumberInputStepDown"]) {
        display: flex !important;
        flex-direction: column-reverse !important;
    }
    [data-testid="stNumberInputStepDown"],
    [data-testid="stNumberInputStepUp"] {
        padding: 0 4px !important;
        min-width: 20px !important;
        width: 24px !important;
    }
    </style>""",
        unsafe_allow_html=True,
    )
