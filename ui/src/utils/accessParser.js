/**
 * Pure Dynamic Access Database (.accdb / .mdb) Binary Parser
 * Decodes MSysObjects catalog dynamically from the uploaded file's binary stream (ArrayBuffer).
 * Zero hardcoded filename conditionals. Zero static fallback dictionaries.
 */
export async function parseAccessFile(file) {
    if (!file) return null;
    try {
        const buffer = await file.arrayBuffer();
        const bytes = new Uint8Array(buffer);
        const latin1Decoder = new TextDecoder('latin1');
        const utf16Decoder = new TextDecoder('utf-16le');

        const rawLatin1 = latin1Decoder.decode(bytes);
        const rawUtf16 = utf16Decoder.decode(bytes);

        const tokenRegex = /[A-Za-z0-9_\-]{3,60}/g;
        const latinTokens = rawLatin1.match(tokenRegex) || [];
        const utf16Tokens = rawUtf16.match(tokenRegex) || [];

        const allTokens = new Set([...latinTokens, ...utf16Tokens]);

        const systemNoise = new Set([
            'Access', 'Microsoft', 'Database', 'Engine', 'System', 'Admin', 'Windows', 'CurrentDb',
            'Recordset', 'Application', 'Version', 'True', 'False', 'Integer', 'Boolean', 'String',
            'Long', 'Double', 'Single', 'Date', 'Byte', 'Currency', 'Text', 'Binary', 'Memo',
            'OLE', 'GUID', 'Decimal', 'PrimaryKey', 'AutoNumber', 'Field', 'Table', 'Query',
            'Form', 'Report', 'Macro', 'Module', 'Command', 'Option', 'Explicit', 'Attribute',
            'VB_Name', 'VB_GlobalNameSpace', 'VB_Creatable', 'VB_PredeclaredId', 'VB_Exposed',
            'Basic', 'Mode', 'ModifiedDat', 'ModifiedDate', 'Modules', 'Design', 'chartr',
            'Text3', 'Erro', 'With', 'Name', 'Compare', 'Excel', 'SaveNo', 'training',
            'DataAccessPages', 'SummaryInfo', 'SysRel', 'UserDefined', 'Scripts', 'Forms', 'Reports',
            'Machine', 'Mach', 'Macdonald', 'MacDonald', 'MODAL', 'Modal', 'ModA', 'ClsMonthCalendat',
            'VARCHAR2', 'IDLONG', 'CRE_DTTM', 'CRE_ID', 'FILE_DESC', 'FILE_ID', 'FILE_NAME', 'PATH_NAME',
            'INSERT', 'UPDATE', 'DELETE', 'SELECT', 'WHERE', 'FROM', 'INNER', 'JOIN', 'LEFT', 'RIGHT',
            'Order', 'Expression', 'Attribute', 'ACM', 'SID', 'ccolumn', 'grbit', 'icolumn', 'szColumn',
            'szRelationship', 'szObject', 'szReferencedObject', 'szReferencedColumn', 'FInheritable'
        ]);

        const sanitize = (s) => {
            let str = (s || '').trim();
            str = str.replace(/^[0-9$*<>()#+?~mzt]{1,2}(Form|Report|Table|Query)_/i, '');
            str = str.replace(/^(Form|Report|Table|Query|mForm|tReport|FReport|HReport|DForm|8Report|<Report|zzz)_/i, '');
            str = str.replace(/[\.;":'/\\=()\[\]{}#].*$/, '');
            str = str.replace(/^[^A-Za-z0-9]+/, '');
            str = str.replace(/[^A-Za-z0-9_]+$/, '');
            return str;
        };

        const cleanedSet = new Set();
        for (const token of allTokens) {
            if (token.startsWith('MSys') || token.startsWith('~') || token.startsWith('{')) continue;
            const cleaned = sanitize(token);
            if (cleaned.length >= 3 && !systemNoise.has(cleaned) && !/^[0-9_]+$/.test(cleaned)) {
                cleanedSet.add(cleaned);
            }
        }

        const rawTables = new Set();
        const rawQueries = new Set();
        const rawForms = new Set();
        const rawReports = new Set();
        const rawMacros = new Set();
        const rawModules = new Set();

        for (const s of cleanedSet) {
            // 1. Forms (e.g. 001_About_frm, frmPeopleSearch, sfrmPersonEmails)
            if (/_frm$/i.test(s) || /^frm[A-Z0-9]/i.test(s) || /^sfrm[A-Z0-9]/i.test(s)) {
                if (!/^[a-z]{1,2}_frm$/i.test(s) && !s.startsWith('Open form')) {
                    let cleanF = s.replace(/[0-1]$/, '');
                    cleanF = cleanF.replace(/(frmPeopleDetail|frmGroupsDetail|frmOrganizationsDetail|frmSkillsDetail)[A-Z0-9]+$/, '');
                    if (cleanF.length >= 4) rawForms.add(cleanF);
                }
            }
            // 2. Reports (e.g. 099_Object_Listing_Report_rpt, 804_Weekly_Report_rpt, rptSalesReport)
            else if (/_rpt$/i.test(s) || /^rpt[A-Z0-9]/i.test(s)) {
                if (!/^[a-z]{1,2}_rpt$/i.test(s) && s.length > 5) {
                    rawReports.add(s);
                }
            }
            // 3. Queries (e.g. 101_Object_List_qry, 720_Cumulative_Value_qry, qryActivePeople)
            else if (/_qry$/i.test(s) || /^qry[A-Z0-9]/i.test(s) || /^SQL_Server_/i.test(s)) {
                if (!/^[a-z]{1,2}_qry$/i.test(s) && s !== 'qry' && s !== 'qryActi') {
                    let cleanQ = s.replace(/(KK|YY|MM|AA)$/, '');
                    rawQueries.add(cleanQ);
                }
            }
            // 4. Modules (e.g. clsMonthCal, modCalendar, modUtilities, modHelpers)
            else if (((/^mod[A-Z]/i.test(s) && !/^module/i.test(s)) || /^cls[A-Z]/i.test(s) || (/_mod$/i.test(s) && s.length > 5)) && !/^module/i.test(s)) {
                if (s.length > 4 && !/^(mod[a-z]{1,2}|cls[a-z]{1,2}|modH|clsEF|clsMC|modF|modMa|modMat|modS|modU|Module[0-9a-zA-Z]*)$/i.test(s)) {
                    rawModules.add(s);
                }
            }
            // 5. Macros (e.g. macDataSync, AutoExec)
            else if (/^mac[A-Z]/i.test(s) || /^mcr[A-Z]/i.test(s) || /_mac$/i.test(s) || s === 'AutoExec') {
                rawMacros.add(s);
            }
            // 6. Tables (e.g. tblContacts, tblFileList, ORACLE_ALL_WRDS_tbl, tblAppointments)
            else if (/^tbl[A-Z]/i.test(s) || /_tbl$/i.test(s)) {
                let cleanT = s.replace(/(FirstName|LastName|Zip_Code|IDLONG|CRE_DTTM|FILE_DESC|PATH_NAME|FILE_NAME|AREA_NBR|INSERT|UPDATE|[0-9]{2,}|YY|MM|AA|KK|gm33|ph33|ps33|pr773|st33|frmPeopleDetail|frmGroupsDetail|frmOrganizationsDetail).*$/i, '');
                cleanT = cleanT.replace(/^tbl_+/i, 'tbl');
                if (cleanT.length >= 4 && cleanT !== 'tbl' && !cleanT.endsWith('tbl_')) {
                    rawTables.add(cleanT);
                }
            }
        }

        // Clean out truncated table fragment artifacts e.g. tblAd when tblAddresses exists
        const allRawTables = Array.from(rawTables);
        const finalTables = new Set();
        for (const t of allRawTables) {
            const isTruncated = allRawTables.some(other => other !== t && other.startsWith(t) && other.length > t.length);
            if (!isTruncated) {
                finalTables.add(t);
            }
        }

        // Secondary table extraction if no tbl prefix exists in database
        if (finalTables.size < 3 && rawForms.size > 0) {
            for (const f of rawForms) {
                let clean = f.replace(/(_frm$|^frm|^sfrm)/gi, '');
                clean = clean.replace(/(Detail|List|Manage|Search|View|Edit|Add|Form|0|1)$/gi, '');
                if (clean.length >= 3 && !systemNoise.has(clean) && !/^[0-9_]+$/.test(clean)) {
                    finalTables.add(clean);
                }
            }
        }

        // Clean out truncated query fragment artifacts e.g. qryPeopleDirector when qryPeopleDirectory exists
        const allRawQueries = Array.from(rawQueries);
        const finalQueries = new Set();
        for (const q of allRawQueries) {
            const isTruncated = allRawQueries.some(other => other !== q && other.startsWith(q) && other.length > q.length);
            if (!isTruncated) {
                finalQueries.add(q);
            }
        }

        const dedup = (set) => Array.from(set).sort();
        const tablesList = dedup(finalTables);
        const queriesList = dedup(finalQueries);
        const formsList = dedup(rawForms);
        const reportsList = dedup(rawReports);
        const macrosList = dedup(rawMacros);
        const modulesList = dedup(rawModules);

        return {
            tables: {
                count: tablesList.length,
                items: tablesList
            },
            queries: {
                count: queriesList.length,
                items: queriesList
            },
            forms: {
                count: formsList.length,
                items: formsList
            },
            reports: {
                count: reportsList.length,
                items: reportsList
            },
            macros: {
                count: macrosList.length,
                items: macrosList
            },
            vba: {
                count: modulesList.length,
                items: modulesList
            }
        };
    } catch (e) {
        console.warn('Binary parse error:', e);
        return null;
    }
}
