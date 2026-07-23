{{- define "k8s-troubleshooter.name" -}}
{{- .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "k8s-troubleshooter.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name (include "k8s-troubleshooter.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "k8s-troubleshooter.labels" -}}
app.kubernetes.io/name: {{ include "k8s-troubleshooter.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
{{- end -}}

{{- define "k8s-troubleshooter.selectorLabels" -}}
app.kubernetes.io/name: {{ include "k8s-troubleshooter.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "k8s-troubleshooter.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "k8s-troubleshooter.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}

{{- define "k8s-troubleshooter.secretName" -}}
{{- if .Values.secrets.existingSecret -}}
{{- .Values.secrets.existingSecret -}}
{{- else -}}
{{- printf "%s-secrets" (include "k8s-troubleshooter.fullname" .) -}}
{{- end -}}
{{- end -}}
