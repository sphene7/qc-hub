"""
Smart view recommendations - analyze sheet relationships and suggest integration.
Add this to the end of semantics.py
"""


def _build_smart_views(sheets: list[dict], joins: list[dict]) -> dict:
    """
    Analyze sheets and their relationships to recommend smart integrated views.
    
    Returns recommendations for:
    - Which sheets should be primary views
    - Which sheets should be embedded as lookups
    - Which sheets can be hidden
    """
    # Classify sheets by role
    main_sheets = []  # Large fact tables with actual data
    lookup_sheets = []  # Reference/configuration tables
    dashboard_sheets = []  # Charts and summaries
    utility_sheets = []  # Instructions, empty, hidden
    
    # Build reference map: which sheets are referenced by others
    referenced_by = {}  # sheet_name -> [list of sheets that reference it]
    for join in joins:
        to_sheet = join.get('to_sheet')
        from_sheet = join.get('from_sheet')
        if to_sheet and from_sheet:
            if to_sheet not in referenced_by:
                referenced_by[to_sheet] = []
            referenced_by[to_sheet].append(from_sheet)
    
    for sheet in sheets:
        name = sheet['name']
        kind = sheet.get('kind', 'table')
        row_count = sheet.get('row_count', 0)
        is_empty = sheet.get('empty', False)
        
        # Classify
        if is_empty or kind in ('instruction', 'hidden'):
            utility_sheets.append({
                'name': name,
                'reason': 'empty或说明表',
                'action': 'hide'
            })
        elif kind == 'dashboard':
            dashboard_sheets.append({
                'name': name,
                'reason': '看板/图表',
                'action': 'optional'
            })
        elif kind == 'lookup' or (kind == 'table' and row_count < 100 and name in referenced_by):
            # Lookup table or small table that's referenced by others
            lookup_sheets.append({
                'name': name,
                'reason': f'被{len(referenced_by.get(name, []))}个表引用' if name in referenced_by else '配置表',
                'action': 'embed',
                'referenced_by': referenced_by.get(name, [])
            })
        elif kind == 'fact' and row_count > 50:
            # Main data table
            main_sheets.append({
                'name': name,
                'reason': f'主数据表 ({row_count}行)',
                'action': 'primary',
                'row_count': row_count,
                'uses_lookups': [j['to_sheet'] for j in joins if j.get('from_sheet') == name]
            })
        else:
            # Other tables - show but not primary
            main_sheets.append({
                'name': name,
                'reason': f'数据表 ({row_count}行)',
                'action': 'show',
                'row_count': row_count
            })
    
    # Sort main sheets by row count (most data first)
    main_sheets.sort(key=lambda x: x.get('row_count', 0), reverse=True)
    
    # Generate recommendations
    recommendations = []
    
    if main_sheets:
        primary_sheet = main_sheets[0]
        rec = {
            'title': f"推荐主视图：{primary_sheet['name']}",
            'description': f"作为主数据表展示（{primary_sheet['row_count']}行数据）",
            'main_sheet': primary_sheet['name'],
            'embed_lookups': [l['name'] for l in lookup_sheets if primary_sheet['name'] in l.get('referenced_by', [])],
            'priority': 'high'
        }
        if rec['embed_lookups']:
            rec['description'] += f"，自动关联 {len(rec['embed_lookups'])} 个配置表"
        recommendations.append(rec)
    
    # Additional fact tables
    for sheet in main_sheets[1:]:
        if sheet.get('action') == 'primary':
            rec = {
                'title': f"次要视图：{sheet['name']}",
                'description': f"另一个主要数据表（{sheet['row_count']}行）",
                'main_sheet': sheet['name'],
                'embed_lookups': [l['name'] for l in lookup_sheets if sheet['name'] in l.get('referenced_by', [])],
                'priority': 'medium'
            }
            recommendations.append(rec)
    
    return {
        'has_recommendations': len(recommendations) > 0,
        'recommendations': recommendations,
        'analysis': {
            'main_sheets': len(main_sheets),
            'lookup_sheets': len(lookup_sheets),
            'dashboard_sheets': len(dashboard_sheets),
            'utility_sheets': len(utility_sheets),
        },
        'details': {
            'main': main_sheets,
            'lookup': lookup_sheets,
            'dashboard': dashboard_sheets,
            'utility': utility_sheets,
        }
    }
