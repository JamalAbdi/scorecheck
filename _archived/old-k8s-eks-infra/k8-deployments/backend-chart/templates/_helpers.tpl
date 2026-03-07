{{- define "scorecheck-backend.name" -}}
scorecheck-backend
{{- end -}}

{{- define "scorecheck-backend.fullname" -}}
{{- printf "%s" (include "scorecheck-backend.name" .) -}}
{{- end -}}
