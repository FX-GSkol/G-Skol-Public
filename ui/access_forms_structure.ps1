param(
    [Parameter(Mandatory=$true)]
    [string]$DatabasePath
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)

function Emit-JsonBase64($obj) {
    $json = $obj | ConvertTo-Json -Depth 12 -Compress
    $bytes = [Text.Encoding]::UTF8.GetBytes($json)
    Write-Output ("MM3FORMS:" + [Convert]::ToBase64String($bytes))
}

$access = $null
$db = $null

try {
    $access = New-Object -ComObject Access.Application
    $access.Visible = $false
    $access.OpenCurrentDatabase($DatabasePath)

    $queries = @()
    try {
        $db = $access.CurrentDb()
        foreach ($qd in @($db.QueryDefs)) {
            $name = [string]$qd.Name
            if ($name -like "~*") { continue }
            $sql = ""
            try { $sql = [string]$qd.SQL } catch {}
            $queries += [PSCustomObject]@{
                name = $name
                sql = $sql
            }
        }
    } catch {}

    $forms = @()
    foreach ($formInfo in @($access.CurrentProject.AllForms)) {
        $formName = [string]$formInfo.Name
        $opened = $false

        try {
            # acViewDesign = 1 ; acHidden = 1
            $access.DoCmd.OpenForm($formName, 1, $null, $null, $null, 1)
            $opened = $true
            $form = $access.Forms.Item($formName)

            $recordSource = ""
            $formCaption = ""
            $defaultView = $null
            $orderBy = ""
            $orderByOn = $false
            try { $recordSource = [string]$form.RecordSource } catch {}
            try { $formCaption = [string]$form.Caption } catch {}
            try { $defaultView = [int]$form.DefaultView } catch {}
            try { $orderBy = [string]$form.OrderBy } catch {}
            try { $orderByOn = [bool]$form.OrderByOn } catch {}

            $controls = @()
            foreach ($ctrl in @($form.Controls)) {
                $name = ""
                $label = ""
                $controlSource = ""
                $rowSource = ""
                $sourceObject = ""
                $linkMaster = ""
                $linkChild = ""
                $controlType = $null
                $tabIndex = $null
                $tabStop = $null
                $section = $null
                $visible = $null
                $enabled = $null
                $left = $null
                $top = $null

                try { $name = [string]$ctrl.Name } catch {}
                try { $controlType = [int]$ctrl.ControlType } catch {}
                try { $controlSource = [string]$ctrl.ControlSource } catch {}
                try { $rowSource = [string]$ctrl.RowSource } catch {}
                try { $sourceObject = [string]$ctrl.SourceObject } catch {}
                try { $linkMaster = [string]$ctrl.LinkMasterFields } catch {}
                try { $linkChild = [string]$ctrl.LinkChildFields } catch {}
                try { $tabIndex = [int]$ctrl.TabIndex } catch {}
                try { $tabStop = [bool]$ctrl.TabStop } catch {}
                try { $section = [int]$ctrl.Section } catch {}
                try { $visible = [bool]$ctrl.Visible } catch {}
                try { $enabled = [bool]$ctrl.Enabled } catch {}
                try { $left = [long]$ctrl.Left } catch {}
                try { $top = [long]$ctrl.Top } catch {}

                # Libellé attaché au contrôle si Access l'expose.
                try {
                    if ($ctrl.Controls.Count -gt 0) {
                        $label = [string]$ctrl.Controls.Item(0).Caption
                    }
                } catch {}
                if (-not $label) {
                    try { $label = [string]$ctrl.Caption } catch {}
                }

                $controls += [PSCustomObject]@{
                    name = $name
                    label = $label
                    control_source = $controlSource
                    row_source = $rowSource
                    source_object = $sourceObject
                    link_master_fields = $linkMaster
                    link_child_fields = $linkChild
                    control_type = $controlType
                    tab_index = $tabIndex
                    tab_stop = $tabStop
                    section = $section
                    visible = $visible
                    enabled = $enabled
                    left = $left
                    top = $top
                }
            }

            $forms += [PSCustomObject]@{
                name = $formName
                caption = $formCaption
                default_view = $defaultView
                record_source = $recordSource
                order_by = $orderBy
                order_by_on = $orderByOn
                controls = $controls
            }

        } catch {
            # Un formulaire atypique n'empêche pas les autres d'être lus.
        } finally {
            if ($opened) {
                try {
                    # acForm = 2 ; acSaveNo = 2
                    $access.DoCmd.Close(2, $formName, 2)
                } catch {}
            }
        }
    }

    Emit-JsonBase64 ([PSCustomObject]@{
        forms = $forms
        queries = $queries
        warning = $null
    })

} catch {
    Emit-JsonBase64 ([PSCustomObject]@{
        forms = @()
        queries = @()
        warning = [string]$_.Exception.Message
    })
} finally {
    try { if ($db) { $db.Close() } } catch {}
    try { if ($access) { $access.CloseCurrentDatabase() } } catch {}
    try { if ($access) { $access.Quit() } } catch {}
}
