Option Explicit

Dim dbPath, outputPath, accessApp, db, fso, outFile
Dim formInfo, formName, formObj, ctrl, qd, opened

If WScript.Arguments.Count < 2 Then WScript.Quit 2
dbPath = WScript.Arguments(0)
outputPath = WScript.Arguments(1)

Set fso = CreateObject("Scripting.FileSystemObject")
On Error Resume Next
Set accessApp = CreateObject("Access.Application")
If Err.Number <> 0 Or accessApp Is Nothing Then
    WScript.Echo "Microsoft Access n'a pas pu etre demarre."
    WScript.Quit 4
End If
Err.Clear
accessApp.Visible = False
accessApp.OpenCurrentDatabase dbPath
If Err.Number <> 0 Then
    WScript.Echo "Impossible d'ouvrir la base Access."
    accessApp.Quit
    WScript.Quit 5
End If
Set db = accessApp.CurrentDb
On Error GoTo 0

Set outFile = fso.CreateTextFile(outputPath, True, True)
outFile.WriteLine "<?xml version=""1.0"" encoding=""utf-16""?>"
outFile.WriteLine "<access_forms>"

' Requetes : utiles lorsque RecordSource est le nom d'une requete.
On Error Resume Next
For Each qd In db.QueryDefs
    If Left(CStr(qd.Name), 1) <> "~" Then
        outFile.WriteLine "  <query name=""" & X(CStr(qd.Name)) & """ sql=""" & X(CStr(qd.SQL)) & """ />"
    End If
Next
On Error GoTo 0

' Formulaires et sous-formulaires : on ouvre en mode Creation, cache.
For Each formInfo In accessApp.CurrentProject.AllForms
    formName = CStr(formInfo.Name)
    opened = False
    On Error Resume Next
    accessApp.DoCmd.OpenForm formName, 1, , , , 1
    If Err.Number = 0 Then opened = True
    Err.Clear
    Set formObj = Nothing
    Set formObj = accessApp.Forms.Item(formName)
    If Not formObj Is Nothing Then
        outFile.Write "  <form"
        outFile.Write " name=""" & X(formName) & """"
        outFile.Write " caption=""" & X(SafeProp(formObj, "Caption")) & """"
        outFile.Write " default_view=""" & X(SafeProp(formObj, "DefaultView")) & """"
        outFile.Write " record_source=""" & X(SafeProp(formObj, "RecordSource")) & """"
        outFile.Write " order_by=""" & X(SafeProp(formObj, "OrderBy")) & """"
        outFile.Write " order_by_on=""" & Bool01(SafeProp(formObj, "OrderByOn")) & """"
        outFile.WriteLine ">"

        For Each ctrl In formObj.Controls
            outFile.Write "    <control"
            outFile.Write " name=""" & X(SafeProp(ctrl, "Name")) & """"
            outFile.Write " label=""" & X(ControlLabel(ctrl)) & """"
            outFile.Write " control_source=""" & X(SafeProp(ctrl, "ControlSource")) & """"
            outFile.Write " row_source=""" & X(SafeProp(ctrl, "RowSource")) & """"
            outFile.Write " source_object=""" & X(SafeProp(ctrl, "SourceObject")) & """"
            outFile.Write " link_master_fields=""" & X(SafeProp(ctrl, "LinkMasterFields")) & """"
            outFile.Write " link_child_fields=""" & X(SafeProp(ctrl, "LinkChildFields")) & """"
            outFile.Write " control_type=""" & X(SafeProp(ctrl, "ControlType")) & """"
            outFile.Write " tab_index=""" & X(SafeProp(ctrl, "TabIndex")) & """"
            outFile.Write " tab_stop=""" & Bool01(SafeProp(ctrl, "TabStop")) & """"
            outFile.Write " section=""" & X(SafeProp(ctrl, "Section")) & """"
            outFile.Write " visible=""" & Bool01(SafeProp(ctrl, "Visible")) & """"
            outFile.Write " enabled=""" & Bool01(SafeProp(ctrl, "Enabled")) & """"
            outFile.Write " left=""" & X(SafeProp(ctrl, "Left")) & """"
            outFile.Write " top=""" & X(SafeProp(ctrl, "Top")) & """"
            outFile.WriteLine " />"
        Next
        outFile.WriteLine "  </form>"
    End If
    Set formObj = Nothing
    If opened Then accessApp.DoCmd.Close 2, formName, 2
    Err.Clear
    On Error GoTo 0
Next

outFile.WriteLine "</access_forms>"
outFile.Close

On Error Resume Next
db.Close
accessApp.CloseCurrentDatabase
accessApp.Quit
On Error GoTo 0
WScript.Quit 0

Function SafeProp(obj, propName)
    Dim v
    On Error Resume Next
    v = ""
    v = CallByNameCompat(obj, propName)
    If Err.Number <> 0 Then Err.Clear: v = ""
    On Error GoTo 0
    SafeProp = v
End Function

Function CallByNameCompat(obj, propName)
    On Error Resume Next
    CallByNameCompat = obj.Properties(propName).Value
    If Err.Number <> 0 Then
        Err.Clear
        CallByNameCompat = ""
    End If
    On Error GoTo 0
End Function

Function ControlLabel(ctrl)
    Dim txt
    txt = ""
    On Error Resume Next
    If ctrl.Controls.Count > 0 Then txt = CStr(ctrl.Controls.Item(0).Caption)
    If Err.Number <> 0 Then Err.Clear
    If Len(txt) = 0 Then txt = CStr(ctrl.Properties("Caption").Value)
    If Err.Number <> 0 Then Err.Clear: txt = ""
    On Error GoTo 0
    ControlLabel = txt
End Function

Function Bool01(v)
    On Error Resume Next
    If CBool(v) Then
        Bool01 = "1"
    Else
        Bool01 = "0"
    End If
    If Err.Number <> 0 Then Err.Clear: Bool01 = "0"
    On Error GoTo 0
End Function

Function X(s)
    Dim t
    t = CStr(s)
    t = Replace(t, "&", "&amp;")
    t = Replace(t, """", "&quot;")
    t = Replace(t, "<", "&lt;")
    t = Replace(t, ">", "&gt;")
    X = t
End Function
