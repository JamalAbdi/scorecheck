{{- define "scorecheck-frontend.name" -}}
scorecheck-frontend
{{- end -}}

{{- define "scorecheck-frontend.fullname" -}}
{{- printf "%s" (include "scorecheck-frontend.name" .) -}}
{{- end -}}
