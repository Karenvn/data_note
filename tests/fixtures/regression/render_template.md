# Regression snapshot for {{ species }}

bioproject: {{ bioproject }}
tolid: {{ tolid }}
assemblies_type: {{ assemblies_type }}
auto_text: {{ auto_text }}

figure_keys:
- Fig_2_Gscope={{ Fig_2_Gscope or "N/A" }}
- Fig_3_Pretext={{ Fig_3_Pretext or "N/A" }}
- Fig_4_Merian={{ Fig_4_Merian or "N/A" }}
- Fig_4_Merqury={{ Fig_4_Merqury or "N/A" }}
- Fig_5_Merqury={{ Fig_5_Merqury or "N/A" }}
- Fig_5_Snail={{ Fig_5_Snail or "N/A" }}
- Fig_6_Snail={{ Fig_6_Snail or "N/A" }}
- Fig_6_Blob={{ Fig_6_Blob or "N/A" }}
- Fig_7_Blob={{ Fig_7_Blob or "N/A" }}

table_keys: {{ tables.keys() | list | join(", ") }}
table1_headers: {{ tables.table1.native_headers | join(" | ") }}
table1_rows: {{ tables.table1.native_rows | length }}
table2_caption: {{ tables.table2.caption }}
table2_headers: {{ tables.table2.native_headers | join(" | ") }}
table2_rows: {{ tables.table2.native_rows | length }}
table2_first: {{ tables.table2.native_rows[0] | join(" | ") if tables.table2.native_rows else "NONE" }}
table3_caption: {{ tables.table3.caption }}
table3_headers: {{ tables.table3.native_headers | join(" | ") }}
table3_rows: {{ tables.table3.native_rows | length }}
table3_first: {{ tables.table3.native_rows[0] | join(" | ") if tables.table3.native_rows else "NONE" }}
table4_caption: {{ tables.table4.caption }}
table4_rows: {{ tables.table4.native_rows | length }}
table5_caption: {{ tables.table5.caption }}
table5_rows: {{ tables.table5.native_rows | length }}
