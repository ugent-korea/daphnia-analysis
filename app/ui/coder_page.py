import streamlit as st
from app.core import database, coder, utils

def render():
    st.title("Daphnia Coding Protocol")
    st.markdown("### Daphnia Magna TEAM 2.0")

    meta = database.get_data()["meta"]
    st.caption(
        f"Last refresh (KST): {utils.last_refresh_kst(meta, 'broods_last_refresh')} • "
        f"Rows: {meta.get('broods_row_count', '?')} • Schema: {meta.get('broods_schema', 'unknown').capitalize()}"
    )

    mother_input = st.text_input(
        "Enter MotherID (core or full)", placeholder="e.g., E.1 or E.1_0804"
    ).strip()

    date_append = st.text_input("Date suffix (_MMDD)", value=utils.today_suffix())

    if mother_input:
        parent, resolved_full_id = coder.get_mother_row(mother_input)
        if not parent:
            st.error("MotherID not found.")
            return

        st.caption(
            f"Matched parent: `{resolved_full_id}` "
            f"(core normalized: `{coder.canonical_core(resolved_full_id)}`)"
        )

        children = coder.get_children_ids(resolved_full_id)
        suggested_core, should_discard, basis = coder.compute_child_and_discard(parent, children)
        suffix = (date_append or "").strip() or utils.today_suffix()
        final_child = suggested_core + suffix

        assigned = parent.get("assigned_person", "unknown") or "unknown"
        set_label = parent.get("set_label", "unknown") or "unknown"

        st.subheader("Result")
        st.write(f"**Set:** {set_label} • **Assignee:** {assigned}")
        st.success(f"**Suggested Child ID:** {final_child}")

        if should_discard:
            st.error("Discard? Yes")
        else:
            st.write("**Discard?** No")

        st.caption(basis)

        with st.expander("Parent details"):
            st.json(parent)

        with st.expander("Existing children (origin = this MotherID)"):
            st.write(children if children else "None")
