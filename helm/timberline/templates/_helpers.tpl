{{/*
Expand the name of the chart.
*/}}
{{- define "timberline.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "timberline.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "timberline.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "timberline.labels" -}}
helm.sh/chart: {{ include "timberline.chart" . }}
{{ include "timberline.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "timberline.selectorLabels" -}}
app.kubernetes.io/name: {{ include "timberline.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Component-specific labels
*/}}
{{- define "timberline.componentLabels" -}}
{{- $component := . -}}
app: {{ $component }}
{{- end }}

{{/*
Fluent Bit labels
*/}}
{{- define "timberline.fluentBit.labels" -}}
{{ include "timberline.labels" . }}
{{ include "timberline.componentLabels" "fluent-bit" }}
{{- end }}

{{/*
Log Ingestor labels
*/}}
{{- define "timberline.logIngestor.labels" -}}
{{ include "timberline.labels" . }}
{{ include "timberline.componentLabels" "log-ingestor" }}
{{- end }}

{{/*
Milvus labels
*/}}
{{- define "timberline.milvus.labels" -}}
{{ include "timberline.labels" . }}
{{ include "timberline.componentLabels" "milvus" }}
{{- end }}

{{/*
etcd labels
*/}}
{{- define "timberline.etcd.labels" -}}
{{ include "timberline.labels" . }}
{{ include "timberline.componentLabels" "etcd" }}
{{- end }}

{{/*
MinIO labels
*/}}
{{- define "timberline.minio.labels" -}}
{{ include "timberline.labels" . }}
{{ include "timberline.componentLabels" "minio" }}
{{- end }}

{{/*
PostgreSQL labels
*/}}
{{- define "timberline.postgresql.labels" -}}
{{ include "timberline.labels" . }}
{{ include "timberline.componentLabels" "postgresql" }}
{{- end }}

{{/*
LLM Chat labels
*/}}
{{- define "timberline.llmChat.labels" -}}
{{ include "timberline.labels" . }}
{{ include "timberline.componentLabels" "llama-cpp-chat" }}
{{- end }}

{{/*
Embedding Service labels
*/}}
{{- define "timberline.embeddingService.labels" -}}
{{ include "timberline.labels" . }}
{{ include "timberline.componentLabels" "llama-cpp-embedding" }}
{{- end }}

{{/*
Attu labels
*/}}
{{- define "timberline.attu.labels" -}}
{{ include "timberline.labels" . }}
{{ include "timberline.componentLabels" "attu" }}
{{- end }}

{{/*
AI Analyzer labels
*/}}
{{- define "timberline.aiAnalyzer.labels" -}}
{{ include "timberline.labels" . }}
{{ include "timberline.componentLabels" "ai-analyzer" }}
{{- end }}

{{/*
Web UI labels
*/}}
{{- define "timberline.webUI.labels" -}}
{{ include "timberline.labels" . }}
{{ include "timberline.componentLabels" "web-ui" }}
{{- end }}

{{/*
Get Milvus host
*/}}
{{- define "timberline.milvus.host" -}}
{{- if .Values.milvus.external.enabled -}}
{{- .Values.milvus.external.host }}
{{- else -}}
milvus
{{- end -}}
{{- end }}

{{/*
Get Milvus port
*/}}
{{- define "timberline.milvus.port" -}}
{{- if .Values.milvus.external.enabled -}}
{{- .Values.milvus.external.port }}
{{- else -}}
19530
{{- end -}}
{{- end }}

{{/*
Get Milvus address
*/}}
{{- define "timberline.milvus.address" -}}
{{- printf "%s:%s" (include "timberline.milvus.host" .) (include "timberline.milvus.port" . | toString) }}
{{- end }}

{{/*
Get Embedding endpoint
*/}}
{{- define "timberline.embedding.endpoint" -}}
{{- if .Values.embeddingService.external.enabled -}}
{{- .Values.embeddingService.external.endpoint }}
{{- else -}}
{{- printf "http://llama-cpp-embedding:%d/embedding" (.Values.embeddingService.config.port | int) }}
{{- end -}}
{{- end }}

{{/*
Get LLM Chat endpoint
*/}}
{{- define "timberline.llmChat.endpoint" -}}
{{- if .Values.llmChat.external.enabled -}}
{{- .Values.llmChat.external.endpoint }}
{{- else -}}
{{- printf "http://llama-cpp-chat:%d" (.Values.llmChat.config.port | int) }}
{{- end -}}
{{- end }}

{{/*
Get PostgreSQL host
*/}}
{{- define "timberline.postgresql.host" -}}
{{- if .Values.postgresql.external.enabled -}}
{{- .Values.postgresql.external.host }}
{{- else -}}
postgresql
{{- end -}}
{{- end }}

{{/*
Get PostgreSQL port
*/}}
{{- define "timberline.postgresql.port" -}}
{{- if .Values.postgresql.external.enabled -}}
{{- .Values.postgresql.external.port }}
{{- else -}}
{{- .Values.postgresql.service.port }}
{{- end -}}
{{- end }}

{{/*
Get PostgreSQL database
*/}}
{{- define "timberline.postgresql.database" -}}
{{- if .Values.postgresql.external.enabled -}}
{{- .Values.postgresql.external.database }}
{{- else -}}
{{- .Values.postgresql.auth.database }}
{{- end -}}
{{- end }}

{{/*
Get PostgreSQL username
*/}}
{{- define "timberline.postgresql.username" -}}
{{- if .Values.postgresql.external.enabled -}}
{{- .Values.postgresql.external.username }}
{{- else -}}
{{- .Values.postgresql.auth.username }}
{{- end -}}
{{- end }}

{{/*
Get PostgreSQL password
*/}}
{{- define "timberline.postgresql.password" -}}
{{- if .Values.postgresql.external.enabled -}}
{{- .Values.postgresql.external.password }}
{{- else -}}
{{- .Values.postgresql.auth.password }}
{{- end -}}
{{- end }}

{{/*
Get PostgreSQL connection URL
*/}}
{{- define "timberline.postgresql.url" -}}
{{- if .Values.postgresql.external.enabled -}}
{{- printf "postgresql://%s:%s@%s:%d/%s" .Values.postgresql.external.username .Values.postgresql.external.password .Values.postgresql.external.host (.Values.postgresql.external.port | int) .Values.postgresql.external.database }}
{{- else -}}
{{- printf "postgresql://%s:%s@postgresql:%d/%s" .Values.postgresql.auth.username .Values.postgresql.auth.password (.Values.postgresql.service.port | int) .Values.postgresql.auth.database }}
{{- end -}}
{{- end }}

{{/*
Get AI Analyzer API endpoint
*/}}
{{- define "timberline.aiAnalyzer.endpoint" -}}
{{- if .Values.aiAnalyzer.config.apiEndpoint -}}
{{- .Values.aiAnalyzer.config.apiEndpoint }}
{{- else -}}
{{- printf "http://ai-analyzer:%d" (.Values.aiAnalyzer.service.port | int) }}
{{- end -}}
{{- end }}
