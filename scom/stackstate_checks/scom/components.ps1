$relations = Get-SCOMRelationshipInstance 
$source_name = ($relations).get_SourceObject() | select id
$target_name = ($relations).get_TargetObject() | select id
$components = $source_name + $target_name |  select id -Unique
$components_list = New-Object System.Collections.Generic.List[System.Object]
For ($i=0; $i -$components.Length; $i++) {
     [string[]] $cmp = Get-SCOMClassInstance -id $components[$i].id |  Select  * -ExcludeProperty Values,ManagementGroup  | ConvertTo-Json -Depth  1
     if ($i -eq $components.Length-1)
    { $components_list.Add($cmp)}
    else{$components_list.Add($cmp+",")} 
    }
"["+($components_list| Out-String )+"]"