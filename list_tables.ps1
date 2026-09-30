$connString = 'Provider=Microsoft.ACE.OLEDB.12.0;Data Source=C:\Users\Afzal\Downloads\Hospital_Management_System.accdb;'
$conn = New-Object System.Data.OleDb.OleDbConnection($connString)
$conn.Open()
$schema = $conn.GetSchema('Tables')

foreach ($row in $schema) {
    if ($row.TABLE_TYPE -eq 'TABLE' -and $row.TABLE_NAME -notlike 'MSys*') {
        $tableName = $row.TABLE_NAME
        $cmd = $conn.CreateCommand()
        $cmd.CommandText = "SELECT COUNT(*) FROM [$tableName]"
        $count = $cmd.ExecuteScalar()
        Write-Output "$tableName : $count"
    }
}
$conn.Close()
