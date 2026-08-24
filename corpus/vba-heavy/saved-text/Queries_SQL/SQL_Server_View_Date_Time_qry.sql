CREATE VIEW [dbo].[Time_View]
/*'--------------------------------------------------------------------------------------------------------------------
' Purpose:				Creates time recordset in different formats from a function
' Parameters:			@StartAt DATETIME, @EndAt DATETIME, @Gap INT = 1
'
' Ver.	Date			Author				Details
' 1.00	30-Jul-2008		Anthony Duguid   	Initial version.
' 1.01	13-Aug-2008		Anthony Duguid		
'--------------------------------------------------------------------------------------------------------------------
*/

/*
SELECT 
DatePart(dw, autokey)
FROM 
gettimelist('2008-08-28', '2008-08-28', 1)

SELECT 
*
FROM 
Time
WHERE pk_date = '28-AUG-2008'
*/

AS

Select 
  convert(datetime, autokey, 21) AS PK_Date 
--yyyy-mm-dd hh:mm:ss.mmm	2008-07-30 00:00:00.000	

, DateName(dw, autokey) 
   + ',' + Space(1) + DateName(m, autokey) 
   + Space(1) + Cast(DAY(autokey) AS VARCHAR(2)) 
   + ',' + Space(1) + Cast(Year(autokey) AS CHAR(4)) AS Date_Name
--ddd, mmm dd yyyy			Wednesday, July 30 2008	

, convert(datetime, convert(varchar, year(autokey)) + '-01-01') AS Year
--yyyy-01-01 00:00:00.000	2008-01-01 00:00:00.000	

, 'Calendar' + Space(1) + convert(varchar, year(autokey)) AS Year_Name
--Calendar yyyy				Calendar 2008	

, convert(datetime, CAST(YEAR(autokey) AS VARCHAR(4)) + '/' + CAST(DATEPART(Q, autokey) * 3 - 2 AS VARCHAR(2)) + '/01') AS Quarter
--yyyy-mm-dd 00:00:00.000	2008-07-01 00:00:00.000	

, 'Quarter' + Space(1) + convert(varchar,DatePart(q, autokey)) 
	+ ',' + Space(1) + convert(varchar, year(autokey)) AS Quarter_Name
--Quarter q, yyyy			Quarter 3, 2008	

, convert(datetime, LEFT(convert(varchar, autokey, 23), 7) + '-01') AS Month
--yyyy-mm-01 00:00:00.000	2008-07-01 00:00:00.000	

, convert(varchar,DateName(mm, autokey)) + Space(1) + Cast(Year(autokey) AS VARCHAR(4)) AS Month_Name
--mmm yyyy					August 2008

, convert(datetime, LEFT(convert(varchar, autokey+(7-datepart(dw, autokey-1)), 21), 11)) AS Week --Weekending date
--yyyy-mm-dd 00:00:00.000	2008-08-03 00:00:00.000

, LEFT(convert(varchar, autokey+(7-datepart(dw, autokey-1)), 113), 11) AS Week_Name
--dd mmm yyyy				03 Aug 2008	

, convert(int,DatePart(dy, autokey)) AS Day_of_Year
--dy						241	

, 'Day' + Space(1) + convert(varchar,DatePart(dy, autokey)) AS Day_of_Year_Name
--Day dy					Day 241	

, DATEDIFF(day, CAST(YEAR(autokey) AS VARCHAR(4)) + '/' + CAST(DATEPART(Q, autokey) * 3 - 2 AS VARCHAR(2)) + '/01', autokey)+1 AS Day_of_Quarter
--x							30	

, 'Day' + Space(1) + convert(varchar,DATEDIFF(day, CAST(YEAR(autokey) AS VARCHAR(4)) + '/' + CAST(DATEPART(Q, autokey) * 3 - 2 AS VARCHAR(2)) + '/01', autokey)+1) AS Day_of_Quarter_Name
--Day x						Day 30	

, convert(int,DatePart(dd, autokey)) AS Day_of_Month
--dd						28	

, 'Day' + Space(1) + convert(varchar,DatePart(d, autokey)) AS Day_of_Month_Name
--Day dd					Day 28	

, convert(int,DatePart(dw, autokey)) AS Day_of_Week
--dw						4	

, 'Day' + Space(1) + convert(varchar,DatePart(dw, autokey)) AS Day_of_Week_Name
--Day dw					Day 4	

, convert(int,DatePart(ww, autokey)) AS Week_of_Year
--wk						35	

, 'Week' + Space(1) + convert(varchar,DatePart(ww, autokey)) AS Week_of_Year_Name
--Week wk					Week 35	

, convert(int,DatePart(m, autokey)) AS Month_of_Year 
--x							8

, 'Month' + Space(1) + convert(varchar,DatePart(m, autokey)) AS Month_of_Year_Name
--Month x 					Month 8	

, ((MONTH(autokey)-1) % 3)+1 AS Month_of_Quarter
--x							2	

 , 'Month' + Space(1) + convert(varchar, ((MONTH(autokey)-1) % 3)+1) AS Month_of_Quarter_Name
--Month x					Month 2	

, convert(int,DatePart(qq, autokey)) AS Quarter_of_Year
--q							3

, 'Quarter' + Space(1) + convert(varchar,DatePart(qq, autokey)) AS Quarter_of_Year_Name
--Quarter q					Quarter 3

/*set datefirst 1  -- Used for the Weekending on a Sunday
declare @date datetime
select @date = getdate()
select CAST( FLOOR( CAST(dateadd(d, 7-datepart(weekday, @date), @date)  AS FLOAT ) ) AS DATETIME)
*/
								--mmm yyyy					July 2008	
/*

	, Left(Datename(m, getdate()), 3) + ' ''' + Right(DATEPART(year, getdate()), 2) as Month_Year
	-- Mar '09

	, datename(dw, autokey) as 'day' -- as name

	, datepart(dw, autokey-1) as 'day of week' -- as number

	, datepart(dw, autokey-1)-1 as 'days since monday' -- as number

	, 7-datepart(dw, autokey-1) as 'days until sunday' -- as number

	, cast(CONVERT(char(10), (autokey-(datepart(dw, autokey-1)-1)), 110) as datetime) as 'monday'

	, cast(CONVERT(char(10), (autokey+(7-datepart(dw, autokey-1))), 110) as datetime) as 'sunday'
	 
    , DATENAME(dw, autokey) + ',' + SPACE(1) + DATENAME(m, autokey) + SPACE(1) + CAST(DAY(autokey) AS VARCHAR(2)) 
    + ',' + SPACE(1) + CAST(YEAR(autokey) AS CHAR(4)) AS 'LONGDATE'

    , DATENAME(dw, autokey) + ',' + SPACE(1) + DATENAME(m, autokey) + SPACE(1) + CAST(DAY(autokey) AS VARCHAR(2)) + ',' + SPACE(1) + CAST(YEAR(autokey) AS CHAR(4)) 
    + SPACE(1) + RIGHT(CONVERT(CHAR(20), autokey - CONVERT(DATETIME, CONVERT(CHAR(8), autokey, 112)), 22), 11) AS 'LONGDATEANDTIME'

    , LEFT(CONVERT(CHAR(19), autokey, 0), 11) AS 'SHORTDATE'

    , REPLACE(REPLACE(CONVERT(CHAR(19), autokey, 0), 'AM', ' AM'), 'PM', ' PM') AS 'SHORTDATEANDTIME'

    , CAST(DATEDIFF(SECOND, '19700101', autokey) AS VARCHAR(64)) AS 'UNIXTIMESTAMP'

    , CONVERT(CHAR(8), autokey, 112) AS 'YYYYMMDD'

    , CONVERT(CHAR(10), autokey, 23) AS 'YYYY-MM-DD'

    , CONVERT(VARCHAR(8), autokey, 12) AS 'YYMMDD'

    , STUFF(STUFF(CONVERT(VARCHAR(8), autokey, 12), 5, 0, '-'), 3, 0, '-') AS 'YY-MM-DD'

    , REPLACE(CONVERT(CHAR(8), autokey, 10), '-', SPACE(0)) AS 'MMDDYY'

    , CONVERT(CHAR(8), autokey, 10) AS 'MM-DD-YY' 

    , CONVERT(CHAR(8), autokey, 1) AS 'MM/DD/YY'

    , CONVERT(CHAR(10), autokey, 101) AS 'MM/DD/YYYY'

    , REPLACE(CONVERT(CHAR(8), autokey, 3), '/', SPACE(0)) AS 'DDMMYY'

    , REPLACE(CONVERT(CHAR(8), autokey, 3), '/', '-') AS  'DD-MM-YY'

    , CONVERT(CHAR(8), autokey, 3) AS 'DD/MM/YY'

    , CONVERT(CHAR(10), autokey, 103) AS 'DD/MM/YYYY'

    , CONVERT(CHAR(8), autokey, 8) AS  'HH:MM:SS 24'

    , LEFT(CONVERT(VARCHAR(8), autokey, 8), 5) AS 'HH:MM 24'

    , LTRIM(RIGHT(CONVERT(VARCHAR(20), autokey, 22), 11)) AS 'HH:MM:SS 12'

    , LTRIM(SUBSTRING(CONVERT( 
    VARCHAR(20), autokey, 22), 10, 5) 
    + RIGHT(CONVERT(VARCHAR(20), autokey, 22), 3)) AS 'HH:MM 12'
*/

FROM 
gettimelist('2009-01-01', '2009-12-31', DEFAULT

