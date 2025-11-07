import streamlit as st
from app.core import database, coder, utils

def render():
    st.title("Daphnia Coding Protocol")
    st.markdown("### *Daphnia Magna* TEAM 2.0")

    # Load metadata with error handling
    try:
        data = database.get_data()
        meta = data.get("meta", {})

        # Check if meta is empty (ETL hasn't run yet)
        if not meta or 'broods_last_refresh' not in meta:
            st.caption("Last refresh (KST): Not yet synced • Rows: 0 • Schema: Broods")
            st.info("💡 Database not yet populated. Run the ETL workflow to sync data from Google Sheets.")
            return

        # Get metadata values
        last_refresh = utils.last_refresh_kst(meta, 'broods_last_refresh')
        row_count = meta.get('broods_row_count', '0')
        schema = meta.get('broods_schema', 'broods')

        st.caption(
            f"Last refresh (KST): {last_refresh} • "
            f"Rows: {row_count} • Schema: {schema.capitalize()}"
        )

    #     Check for invalid status entries and show prominent warning
    #     invalid_status_raw = meta.get('invalid_status_entries')
    #     if invalid_status_raw:
    #         try:
    #             import ast
    #             invalid_entries = ast.literal_eval(invalid_status_raw)
    #             if invalid_entries:
    #                 st.error(f"⚠️ **DATA QUALITY ALERT: {len(invalid_entries)} brood(s) have invalid status entries!**")
    #                 st.warning(
    #                     "**Status must be ONLY:** `Alive` or `Dead` (case-insensitive)\n\n"
    #                     "**Invalid entries found:**"
    #                 )
    #
    #                 # Group by assigned person for easier fixing
    #                 from collections import defaultdict
    #                 by_person = defaultdict(list)
    #                 for entry in invalid_entries:
    #                     person = entry.get('assigned_person', 'Unknown')
    #                     by_person[person].append(entry)
    #
    #                 for person, entries in sorted(by_person.items()):
    #                     with st.expander(f"👤 **{person}** ({len(entries)} invalid entries)", expanded=True):
    #                         for entry in entries:
    #                             st.markdown(
    #                                 f"- **Mother ID:** `{entry['mother_id']}` | "
    #                                 f"**Set:** {entry['set_label']} | "
    #                                 f"**Invalid Status:** `{entry['status']}`"
    #                             )
    #
    #                 st.info("💡 **Action Required:** Please update the Google Sheets to use only 'Alive' or 'Dead' in the Status column, then run the ETL refresh.")
    #         except Exception as e:
    #             st.error(f"Error parsing invalid status entries: {e}")
    #
    except Exception as e:
        st.caption("Last refresh (KST): Error loading • Rows: ? • Schema: Broods")
        st.error(f"❌ Failed to load database metadata: {e}")
        return

    mother_input = st.text_input(
        "Enter MotherID (core or full)", placeholder="e.g., E.1 or E.1_0804"
    ).strip()

    date_append = st.text_input("Date suffix (_MMDD)", value=utils.today_suffix())

    if mother_input:
        parent, resolved_full_id = coder.get_mother_row(mother_input)
        if not parent:
            st.error("MotherID not found.")
            return

        # Check if mother is dead - show warning at the top
        if not coder.is_mother_alive(parent):
            st.error("⚠️ WARNING: This mother is DEAD. Please verify the mother code.")

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
            # Add experimental note for 3rd broods
            if "3rd subbrood" in basis:
                st.info("💡 Note: Third broods are optimal for experimental use.")

        st.caption(basis)

        with st.expander("Parent details"):
            st.json(parent)

        with st.expander("Existing children (origin = this MotherID)"):
            st.write(children if children else "None")
