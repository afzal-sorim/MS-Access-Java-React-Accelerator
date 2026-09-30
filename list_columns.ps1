$connString = 'Provider=Microsoft.ACE.OLEDB.12.0;Data Source=C:\Users\Afzal\Downloads\Hospital_Management_System.accdb;'
$conn = New-Object System.Data.OleDb.OleDbConnection($connString)
$conn.Open()
$schema = $conn.GetSchema('Columns')

$schema | Where-Object { $_.TABLE_NAME -eq 'Patients' } | Select-Object COLUMN_NAME, DATA_TYPE, IS_NULLABLE | Format-Table
$conn.Close()
