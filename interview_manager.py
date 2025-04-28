# interview_manager.py (Reverted to simpler version)
import random

class InterviewManager:
    """Manages state for a simple Q&A flow without complex follow-ups."""

    def __init__(self, questions):
        if not questions or not isinstance(questions, list):
            raise ValueError("Requires a list of questions.")
        self.questions = questions
        self.current_question_index = -1 # -1: Before Q0
        # Structure: {'question': str, 'answer': str | None, 'evaluation': str | None, 'flag': str | None}
        self.user_responses = []
        # Simpler States: INIT, GREETING, AWAITING_GREETING_RESPONSE, GREETING_ACKNOWLEDGED,
        #                 ASKING_QUESTION, LISTENING, PROCESSING_ANSWER, ACKNOWLEDGED_ANSWER,
        #                 CLOSING, FINISHED
        self.state = "INIT"
        # No follow-up specific fields needed in this version

    def to_dict(self):
        """Serializes state."""
        return {
            'questions': self.questions, 'current_question_index': self.current_question_index,
            'user_responses': self.user_responses, 'state': self.state,
        }

    @classmethod
    def from_dict(cls, data):
        """Deserializes state."""
        if not data or 'questions' not in data: raise ValueError("Invalid data for Manager")
        manager = cls(data['questions'])
        manager.current_question_index = data.get('current_question_index', -1)
        manager.user_responses = data.get('user_responses', [])
        manager.state = data.get('state', "INIT")
        # Ensure backward compatibility if 'follow_ups' exists in old session data, ignore it
        for resp in manager.user_responses:
            resp.pop('follow_ups', None)
        return manager

    def _log_state_change(self, new_state):
        """Logs state transitions."""
        if self.state != new_state:
            print(f"InterviewManager: State {self.state} -> {new_state}")
            self.state = new_state

    def start_interview(self):
        """Transitions from INIT to GREETING."""
        if self.state == "INIT":
            self._log_state_change("GREETING"); return {"state": self.state}
        return None

    def record_greeting_response(self, greeting_response):
         """Records the user's response to the initial greeting."""
         # We might not store this in the final report in this version
         if self.state == "AWAITING_GREETING_RESPONSE":
            print(f"InterviewManager: Recorded greeting response (not stored in log).")
            # Optionally store if needed:
            # self.user_responses.append({"question": "Initial Greeting", "answer": greeting_response, "evaluation": "N/A", "flag": None})
            return True
         return False

    def prepare_first_question(self):
        """Moves state to ASKING_QUESTION for the first question."""
        if self.state == "GREETING_ACKNOWLEDGED":
            if not self.questions: self._log_state_change("CLOSING"); return None
            self.current_question_index = 0
            self._log_state_change("ASKING_QUESTION")
            print(f"Prep Q{self.current_question_index}")
            return self.current_question_index
        print(f"Err: prep first Q in state {self.state}"); return None

    def get_current_question(self):
        """Gets the text of the scheduled question to be asked."""
        if self.state == "ASKING_QUESTION" and 0 <= self.current_question_index < len(self.questions):
            return self.questions[self.current_question_index]
        return None

    def record_answer_and_evaluation(self, answer_text, evaluation_note):
        """Records answer and simple evaluation note. State set by caller."""
        if self.state == "PROCESSING_ANSWER":
            if not (0 <= self.current_question_index < len(self.questions)): return None
            question_asked = self.questions[self.current_question_index]
            flag = "inappropriate" if self._is_inappropriate(answer_text) else None
            self.user_responses.append({
                "question": question_asked, "answer": answer_text,
                "evaluation": evaluation_note, # Store simple note
                "flag": flag
                # No 'follow_ups' field needed here
            })
            print(f"Recorded answer for Q{self.current_question_index}. Eval: '{evaluation_note}'")
            return {"recorded": True}
        print(f"Err: record_answer in state {self.state}"); return None

    def prepare_next_question(self):
        """Moves state to next scheduled question or closing."""
        # Called when previous cycle acknowledged
        if self.state == "ACKNOWLEDGED_ANSWER":
             next_index = self.current_question_index + 1
             if next_index < len(self.questions):
                 self.current_question_index = next_index
                 self._log_state_change("ASKING_QUESTION")
                 return {"state": self.state, "next_question_index": self.current_question_index}
             else: # All questions done
                 self.current_question_index = len(self.questions)
                 self._log_state_change("CLOSING")
                 return {"state": self.state}
        print(f"Error: prep_next_q called in state {self.state}"); return None

    def _is_inappropriate(self, text):
        keywords = ["badword1", "offensive2"]; return any(k in text.lower() for k in keywords)

    def get_final_data(self):
        """Returns report data and ensures state is FINISHED."""
        if self.state in ["CLOSING", "FINISHED"]: self._log_state_change("FINISHED"); return {"responses": self.user_responses}
        print(f"Warn: get_final_data called in state {self.state}"); return None

    def get_state(self): return self.state
    def set_state(self, new_state): self._log_state_change(new_state)

    def get_last_question_asked(self):
         """Gets text of question whose answer is being processed."""
         if self.state == "PROCESSING_ANSWER" and 0 <= self.current_question_index < len(self.questions):
              return self.questions[self.current_question_index]
         return "N/A"