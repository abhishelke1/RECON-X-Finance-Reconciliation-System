import axios from 'axios';

const api = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
});

export interface Merchant {
  id: string;
  name: string;
  razorpay_account_id?: string;
  business_type?: string;
  status: string;
}

export interface ReconciliationRun {
  id: string;
  merchant_id: string;
  status: string;
  started_at: string;
  completed_at?: string;
  total_records: number;
  matched_records: number;
  unmatched_records: number;
  exceptions_found: number;
  auto_resolved: number;
  human_review: number;
  processing_time_ms?: number;
  parameters?: any;
}

export interface ReconciliationMatch {
  id: string;
  run_id: string;
  payment_id?: string;
  order_id?: string;
  settlement_id?: string;
  ledger_entry_id?: string;
  match_status: string;
  match_confidence: number;
  match_reasons?: string[];
  expected_amount?: number;
  actual_amount?: number;
  variance?: number;
  recon_status: string;
}

export interface ExceptionItem {
  id: string;
  run_id: string;
  match_id?: string;
  merchant_id: string;
  exception_type: string;
  severity: string;
  status: string;
  amount_involved?: number;
  variance?: number;
  description: string;
  assigned_to?: string;
  resolved_at?: string;
  created_at: string;
}

export interface ExceptionDetail extends ExceptionItem {
  ai_analysis?: {
    classification: string;
    explanation: string;
    supporting_evidence: string[];
    confidence: number;
    recommended_action: string;
    missing_information: string[];
    requires_human_review: boolean;
  };
  policy_result?: {
    can_auto_resolve: boolean;
    action: string;
    reason: string;
    reviewer_role?: string;
  };
  resolution_notes?: string;
  evidence_graph: {
    exception_id: string;
    nodes: Array<{
      id: string;
      entity_type: string;
      label: string;
      data: any;
    }>;
    edges: Array<{
      source_id: string;
      target_id: string;
      relation: string;
      metadata: any;
    }>;
  };
  decisions: Array<{
    id: string;
    decision_type: string;
    decided_by: string;
    timestamp: string;
    action_taken: string;
    reason: string;
    confidence?: number;
  }>;
}

export interface EvaluationBenchmark {
  dataset_name: string;
  dataset_size: number;
  recon_x: {
    precision: number;
    recall: number;
    f1_score: number;
    auto_resolution_precision: number;
    human_review_rate?: number;
    processing_time_ms: number;
    throughput_per_sec?: number;
  };
  baseline: {
    precision: number;
    recall: number;
    f1_score: number;
    human_review_rate?: number;
    processing_time_ms: number;
  };
  lift?: {
    recall_lift: number;
    f1_lift: number;
    manual_effort_reduction_pct: number;
  };
}

export interface AuditLog {
  id: string;
  entity_id: string;
  entity_type: string;
  action: string;
  actor: string;
  timestamp: string;
  details: any;
  request_id?: string;
}

export default api;
