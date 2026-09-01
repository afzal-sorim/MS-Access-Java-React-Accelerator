SELECT msysobjects.Name, GetObjectTypeName([Type]) AS TypeName, msysobjects.Type, GetObjectDescription([Name]) AS Description, msysobjects.DateUpdate, msysobjects.Connect, msysobjects.DateCreate
FROM msysobjects
WHERE (((msysobjects.Type) Not In (2,3,8,-32757,-32758)) AND ((msysobjects.Name) Not Like '~*' And (msysobjects.Name) Not Like 'Msys*'))
ORDER BY msysobjects.Type, msysobjects.DateUpdate DESC , msysobjects.Name;

