$connString = 'Provider=Microsoft.ACE.OLEDB.12.0;Data Source=C:\Users\Afzal\Downloads\Hospital_Management_System.accdb;'
$conn = New-Object System.Data.OleDb.OleDbConnection($connString)
$conn.Open()

$targetCount = 1000000

$cmd = $conn.CreateCommand()
$cmd.CommandText = "SELECT COUNT(*) FROM Patients"
$currentCount = $cmd.ExecuteScalar()

Write-Output "Initial count: $currentCount"

while ($currentCount -lt $targetCount) {
    # If doubling the count would exceed the target too much, we could limit it using TOP, 
    # but the user said "I don't mind the quality of the data, the existing data can be repeated multiple times to reach the 1 million data count"
    # MS Access SQL supports INSERT INTO ... SELECT ...
    $insertSql = "INSERT INTO Patients (PatientName, Phone, Address, Gender, BloodGroup, DOB) SELECT PatientName, Phone, Address, Gender, BloodGroup, DOB FROM Patients"
    $cmd.CommandText = $insertSql
    try {
        $rowsInserted = $cmd.ExecuteNonQuery()
        $currentCount += $rowsInserted
        Write-Output "Inserted $rowsInserted rows. New count: $currentCount"
    } catch {
        Write-Output "Error: $_"
        break
    }
}

Write-Output "Final count: $currentCount"
$conn.Close()
