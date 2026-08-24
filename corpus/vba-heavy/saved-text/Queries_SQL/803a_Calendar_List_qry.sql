SELECT MsysObjects.DateUpdate, MsysObjects.Name, Format([DateUpdate],"Short Time") AS Time2, MsysObjects.Type, DateValue([DateUpdate]) AS DateMatch
FROM MsysObjects
WHERE (((MsysObjects.Name) Not Like "*~sq*") AND ((MsysObjects.Type) Not In (3,8,-32757,-32758)));

