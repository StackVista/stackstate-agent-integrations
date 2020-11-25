$relations = Get-SCOMRelationshipInstance 
$source_name = ($relations).get_SourceObject() | select id
$target_name = ($relations).get_TargetObject() | select id
$json_relations = $source_name | Foreach {$i=0}{new-object pscustomobject -prop @{source=$_;target=$target_name[$i]}; $i++}  | ConvertTo-Json
$json_relations 