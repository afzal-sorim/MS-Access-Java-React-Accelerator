SELECT CDate(StartOfWeek(DateValue([DateUpdate]),1)) AS WeekOf
FROM msysobjects
GROUP BY CDate(StartOfWeek(DateValue([DateUpdate]),1));

